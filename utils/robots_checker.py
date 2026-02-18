"""RobotsChecker fetches and parses robots.txt for a domain and checks URL allowance.
It caches results per domain for the session to avoid repeated network calls.
"""
import asyncio
from urllib.parse import urlparse
from typing import Dict

try:
    from reppy.robots import Robots
except ImportError:
    Robots = None

class RobotsChecker:
    def __init__(self, valves):
        self.valves = valves
        self.cache: Dict[str, Robots] = {}
        self.respect = getattr(valves, "RESPECT_ROBOTS_TXT", True)

    async def fetch_robots(self, domain: str) -> Robots:
        if domain in self.cache:
            return self.cache[domain]
        url = f"https://{domain}/robots.txt"
        async with asyncio.Semaphore(5):  # limit concurrent fetches
            try:
                import httpx
                async with httpx.AsyncClient() as client:
                    resp = await client.get(url, timeout=10)
                    resp.raise_for_status()
                    txt = resp.text
            except Exception:
                txt = ""
        if Robots:
            robots = Robots.parse(url, txt)
        else:
            # Fallback simple parser: allow all
            class SimpleRobots:
                def allowed(self, user_agent, url_path):
                    return True
            robots = SimpleRobots()
        self.cache[domain] = robots
        return robots

    async def is_allowed(self, url: str, user_agent: str) -> bool:
        if not self.respect:
            return True
        parsed = urlparse(url)
        domain = parsed.netloc
        path = parsed.path or "/"
        robots = await self.fetch_robots(domain)
        # reppy Robots has allowed(useragent, url)
        if hasattr(robots, "allowed"):
            return robots.allowed(user_agent, path)
        # Simple fallback
        return True
