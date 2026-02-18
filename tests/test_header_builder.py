"""Tests for HeaderBuilder"""
import pytest
from utils.header_builder import HeaderBuilder

class DummyValves:
    DEFAULT_USER_AGENT = "TestAgent/1.0"
    EXTRA_HEADERS = {"Accept": "text/html"}
    USER_AGENT_POOL = ["AgentA/1.0", "AgentB/2.0"]

@pytest.fixture
def valves():
    return DummyValves()

def test_default_headers(valves):
    hb = HeaderBuilder(valves)
    headers = hb.get_headers()
    assert headers["User-Agent"] in [valves.DEFAULT_USER_AGENT] + valves.USER_AGENT_POOL
    assert headers["Accept"] == "text/html"

def test_pool_rotation(valves):
    hb = HeaderBuilder(valves)
    # Force pool usage by ensuring pool not empty
    hb.ua_pool = ["A/1", "B/2"]
    seen = set()
    for _ in range(10):
        seen.add(hb.get_headers()["User-Agent"])
    assert seen == set(["A/1", "B/2"])
