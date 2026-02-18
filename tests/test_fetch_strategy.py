"""Tests for FetchStrategy"""
import pytest
import httpx
from utils.fetch_strategy import FetchStrategy

class DummyResponse:
    def __init__(self, text="ok"):
        self.text = text
        self.content = text.encode('utf-8')
        self.status_code = 200
        self.request = httpx.Request('GET', 'http://example.com')
    def raise_for_status(self):
        pass

class DummyClient:
    def __init__(self, fail_first=False):
        self.called = 0
        self.fail_first = fail_first
    async def get(self, url, **kwargs):
        self.called += 1
        if self.fail_first and self.called == 1:
            raise httpx.HTTPStatusError('error', request=httpx.Request('GET', url), response=httpx.Response(500))
        return DummyResponse()

class DummyValves:
    FETCH_RETRY_COUNT = 1
    PROXY_LIST = []
    ENABLE_ADVANCED_FETCH = False
    BROWSER_TIMEOUT_SECONDS = 30
    RESPECT_ROBOTS_TXT = False

@pytest.mark.asyncio
async def test_fetch_success():
    client = DummyClient()
    fs = FetchStrategy(DummyValves(), client)
    resp = await fs.fetch('http://example.com')
    assert isinstance(resp, DummyResponse)
    assert resp.text == 'ok'

@pytest.mark.asyncio
async def test_fetch_retry_on_status_error():
    client = DummyClient(fail_first=True)
    fs = FetchStrategy(DummyValves(), client)
    resp = await fs.fetch('http://example.com')
    assert resp.text == 'ok'
    assert client.called == 2
