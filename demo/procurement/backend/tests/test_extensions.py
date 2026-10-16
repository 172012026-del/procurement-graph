import asyncio
from dataclasses import replace
import importlib.util
import json
from pathlib import Path

import httpx
import pytest

from app import extractor, graph_store
from app.config import settings
from app.database import upsert_notice
from app.retrieval import augment, retrieve


def test_domain_retrieval_returns_rules_and_never_claims_them_as_source():
    assert retrieve('联合体 成员 牵头人',1)[0]['id']=='consortium'
    text, ids, fingerprint = augment('合同包1中联合体成员共同报价')
    assert '不是当前公告事实' in text and '不得用作字段证据' in text
    assert ids and len(fingerprint)==64
    assert retrieve('zzzz-no-overlap')==[]


def test_rag_requests_have_separate_cache_and_cannot_replay_schema_response(tmp_path,monkeypatch):
    base=replace(settings,deepseek_api_key='mock',model_cache_dir=str(tmp_path),extraction_strategy='schema')
    monkeypatch.setattr(extractor,'settings',base)
    requests=[]
    def handler(request):
        requests.append(json.loads(request.content))
        return httpx.Response(200,json={'choices':[{'message':{'content':'{"project_name":"项目","lots":[]}'},'finish_reason':'stop'}]})
    async def run():
        original=extractor.DeepSeekExtractor()
        original.client=httpx.AsyncClient(transport=httpx.MockTransport(handler))
        await original._call('联合体成员报价',['a.html']);await original.close()
        monkeypatch.setattr(extractor,'settings',replace(base,extraction_strategy='rag'))
        replay=extractor.DeepSeekExtractor(cache_only=True)
        with pytest.raises(extractor.FatalModelError,match='缓存未命中'):
            await replay._call('联合体成员报价',['a.html'])
        assert replay.calls==0
        rag=extractor.DeepSeekExtractor()
        rag.client=httpx.AsyncClient(transport=httpx.MockTransport(handler))
        await rag._call('联合体成员报价',['a.html']);await rag.close()
    asyncio.run(run())
    assert len(requests)==2 and '领域参考' not in requests[0]['messages'][1]['content']
    assert '领域参考' in requests[1]['messages'][1]['content']
    assert len(list(tmp_path.glob('*.json')))==2


def test_graph_sync_keeps_failed_bids_and_parameterizes_notice_identity(notice,monkeypatch):
    from app.models import BidExtract
    result=notice()
    result.bids.append(BidExtract(bidder="供应商'丙",review_status='未通过',review_reason='资格不符'))
    upsert_notice(result,['a.html'],'isolated')
    monkeypatch.setattr(graph_store,'settings',replace(settings,neo4j_uri='bolt://unused'))
    calls=[]
    class Tx:
        def run(self,query,**parameters):
            calls.append((query,parameters));return self
        def consume(self): pass
    class Session:
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def execute_write(self,function): return function(Tx())
    monkeypatch.setattr(graph_store,'session',lambda:Session())
    assert graph_store.sync_notice('isolated',result.notice_uuid)
    bid_parameters=next(parameters for query,parameters in calls if 'UNWIND $bids' in query)
    assert len(bid_parameters['bids'])==3
    assert any(row['review_status']=='未通过' for row in bid_parameters['bids'])
    assert all("供应商'丙" not in query for query,_ in calls)
    assert all(parameters.get('dataset')=='isolated' for _,parameters in calls)


def test_graph_missing_or_stale_mirror_returns_service_unavailable(client,notice,monkeypatch):
    from app import config
    upsert_notice(notice(),['a.html'],'isolated')
    monkeypatch.setattr(config,'settings',replace(settings,relation_backend='neo4j'))
    class Tx:
        def run(self,*args,**kwargs): return []
    class Session:
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def execute_read(self,function): return function(Tx())
    monkeypatch.setattr(graph_store,'session',lambda:Session())
    response=client.get('/api/analytics/purchaser-partners',params={'dataset_id':'isolated','purchaser':'采购单位A'})
    assert response.status_code==503 and '过期' in response.json()['detail']


def test_knowledge_endpoint_is_offline_and_respects_auth(client,monkeypatch):
    import app.main as main
    response=client.get('/api/knowledge',params={'q':'审查资格符合性','top_k':1})
    assert response.status_code==200 and response.json()['data'][0]['id']=='review'
    monkeypatch.setattr(main,'settings',replace(settings,api_token='private-test-access'))
    assert client.get('/api/knowledge',params={'q':'金额'}).status_code==401


def load_script(name):
    root=Path(__file__).resolve().parents[4]
    spec=importlib.util.spec_from_file_location(name,root/name)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def test_training_rejects_unreviewed_data_and_cross_split_source(tmp_path):
    module=load_script('training/train_lora.py')
    path=tmp_path/'draft.jsonl'
    path.write_text(json.dumps({'reviewed':False})+'\n',encoding='utf-8')
    with pytest.raises(ValueError,match='human-reviewed'):
        module.read_data(path)
    with pytest.raises(ValueError,match='notice'):
        module.validate([{'notice_uuid':'a','source_sha256':'x'}],[{'notice_uuid':'a','source_sha256':'y'}])
    with pytest.raises(ValueError,match='Identical source'):
        module.validate([{'notice_uuid':'a','source_sha256':'x'}],[{'notice_uuid':'b','source_sha256':'x'}])
