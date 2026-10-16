import asyncio
from dataclasses import replace

import pytest

from app import extractor, main
from app.config import settings
from app.database import one


def test_paused_model_cannot_create_http_client_or_attempt_a_request(monkeypatch):
    monkeypatch.setattr(extractor,'settings',replace(settings,model_network_enabled=False))

    def forbidden(*args,**kwargs):
        raise AssertionError('An HTTP client must not be created while paused')

    monkeypatch.setattr(extractor.httpx,'AsyncClient',forbidden)
    model = extractor.DeepSeekExtractor()
    model.api_key = 'test-placeholder'
    with pytest.raises(extractor.FatalModelError,match='网络调用已暂停'):
        asyncio.run(model._call('local test',['document.html']))
    assert model.calls == 0


def test_paused_model_rejects_local_extraction_before_creating_job(client,monkeypatch):
    monkeypatch.setattr(main,'settings',replace(settings,model_network_enabled=False))
    response = client.post('/api/ingest/local',json={'dataset_id':'test','limit':1,'mode':'extract'})
    assert response.status_code == 503
    assert one('SELECT COUNT(*) count FROM jobs')['count'] == 0


def test_paused_model_rejects_uploaded_extraction(client,monkeypatch):
    monkeypatch.setattr(main,'settings',replace(settings,model_network_enabled=False))
    response = client.post('/api/ingest',data={'mode':'extract'},files={'files':('test.html',b'<p>local</p>','text/html')})
    assert response.status_code == 503
    assert one('SELECT COUNT(*) count FROM jobs')['count'] == 0
