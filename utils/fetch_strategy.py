"""FetchStrategy handles robust fetching with retries, optional proxies, and optional headless browser fallback.
It uses HeaderBuilder for header construction and respects configuration flags.
"""

import random
import asyncio
from typing import Dict, Any, Optional
import httpx
from .header_builder import HeaderBuilder

import re
# Optional import for Playwright; lazy import to avoid heavy dependency if unused
try:
    from playwright.async_api import async_playwright
except ImportError:
    async_playwright = None

class FetchStrategy:
    def __init__(self, valves, client: httpx.AsyncClient):
        self.valves = valves
        self.client = client
        self.header_builder = HeaderBuilder(valves)
        self.retry_count = getattr(valves, "FETCH_RETRY_COUNT", 2)
        self.proxies = getattr(valves, "PROXY_LIST", [])
        self.browser_timeout = getattr(valves, "BROWSER_TIMEOUT_SECONDS", 30)
        self.enable_advanced = getattr(valves, "ENABLE_ADVANCED_FETCH", False)
        self.respect_robots = getattr(valves, "RESPECT_ROBOTS_TXT", True)

    async def fetch(self, url: str) -> httpx.Response:
        """Fetch a URL with retries, optional proxy rotation, and optional browser fallback.
        Returns the httpx.Response on success, raises on failure.
        """
        last_exception: Optional[Exception] = None
        for attempt in range(self.retry_count + 1):
            headers = self.header_builder.get_headers()
            proxy = None
            if self.proxies:
                proxy = random.choice(self.proxies)
                proxy_url = f"http://{proxy}" if not proxy.startswith("http") else proxy
                transport = httpx.AsyncHTTPTransport(proxy=proxy_url)
                client = httpx.AsyncClient(headers=headers, timeout=120, transport=transport, follow_redirects=True)
            else:
                client = self.client
            try:
                response = await client.get(url, headers=headers, timeout=120)
                response.raise_for_status()
                # Detect simple bot challenge pages and fallback if needed
                if self.enable_advanced and self._is_bot_challenge(response.text):
                    # Browser fallback
                    return await self._browser_fetch(url)
                return response
            except Exception as e:
                last_exception = e
                if attempt < self.retry_count:
                    continue
        # All HTTP attempts failed; try browser fallback if enabled
        if self.enable_advanced:
            return await self._browser_fetch(url)
        raise last_exception if last_exception else Exception("Fetch failed without exception")

    def _is_bot_challenge(self, text: str) -> bool:
        """Heuristic to detect Cloudflare/Medium bot verification pages."""
        pattern = r"(?i)just a moment|security verification|cloudflare|performing security verification"
        return bool(re.search(pattern, text))

    async def _browser_fetch(self, url: str) -> httpx.Response:
        """Fetch the page using Playwright headless browser."""
        if not async_playwright:
            raise RuntimeError("Playwright is not available for browser fallback")
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(timeout=self.browser_timeout * 1000)
                page = await browser.new_page()
                await page.goto(url, timeout=self.browser_timeout * 1000)
                content = await page.content()
                response = httpx.Response(200, content=content.encode("utf-8"), request=httpx.Request("GET", url))
                await browser.close()
                return response
        except Exception as be:
            raise be
