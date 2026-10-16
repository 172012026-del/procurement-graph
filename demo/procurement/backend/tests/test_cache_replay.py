import asyncio
from dataclasses import replace

import httpx
import pytest

from app import extractor
from app.config import settings


def test_cache_replay_works_without_key_and_cannot_create_network_client(tmp_path,monkeypatch):
    monkeypatch.setattr(extractor,'settings',replace(settings,model_network_enabled=True,model_cache_dir=str(tmp_path)))
    body={'choices':[{'finish_reason':'stop','message':{'content':'{"project_name":"已缓存的真实响应结构","lots":[]}'}}],
          'usage':{'prompt_tokens':10,'completion_tokens':5,'total_tokens':15}}
    async def prepare():
        model=extractor.DeepSeekExtractor()
        model.api_key='mock-placeholder'
        model.client=httpx.AsyncClient(transport=httpx.MockTransport(lambda request:httpx.Response(200,json=body)))
        await model._call('source content',['a.html'])
        await model.close()
    asyncio.run(prepare())
    monkeypatch.setattr(extractor.httpx,'AsyncClient',lambda *a,**k:pytest.fail('Replay must not create an HTTP client'))
    replay=extractor.DeepSeekExtractor(cache_only=True)
    replay.api_key=''
    record=asyncio.run(replay._call('source content',['a.html']))
    assert record.project_name=='已缓存的真实响应结构'
    assert replay.calls==0 and replay.response_cache_hits==1 and len(replay.response_cache_keys)==1


def test_cache_miss_never_falls_back_to_paid_request(tmp_path,monkeypatch):
    monkeypatch.setattr(extractor,'settings',replace(settings,model_network_enabled=True,model_cache_dir=str(tmp_path)))
    monkeypatch.setattr(extractor.httpx,'AsyncClient',lambda *a,**k:pytest.fail('A cache miss must not create an HTTP client'))
    replay=extractor.DeepSeekExtractor(cache_only=True)
    replay.api_key=''
    with pytest.raises(extractor.FatalModelError,match='缓存未命中'):
        asyncio.run(replay._call('uncached new input',['new.html']))
    assert replay.calls==0
