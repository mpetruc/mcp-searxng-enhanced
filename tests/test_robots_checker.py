"""Tests for RobotsChecker"""
import pytest
from utils.robots_checker import RobotsChecker

class DummyValves:
    RESPECT_ROBOTS_TXT = False
    # other needed attributes can be omitted

@pytest.fixture
def valves():
    return DummyValves()

@pytest.mark.asyncio
async def test_robots_disabled(valves):
    rc = RobotsChecker(valves)
    allowed = await rc.is_allowed('https://example.com/some/page', 'TestAgent')
    assert allowed is True
