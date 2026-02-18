"""HeaderBuilder constructs request headers for web fetching.
It supports a default User-Agent and optional rotation through a pool.
Configuration values are read from Tools.valves.
"""

from typing import Dict, List
import random

class HeaderBuilder:
    def __init__(self, valves):
        self.valves = valves
        # Base headers always sent
        self.base_headers = {
            "User-Agent": getattr(valves, "DEFAULT_USER_AGENT", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3")
        }
        # Optional extra headers from config
        extra = getattr(valves, "EXTRA_HEADERS", {})
        if isinstance(extra, dict):
            self.base_headers.update(extra)
        # Optional pool of User-Agents for rotation
        self.ua_pool: List[str] = getattr(valves, "USER_AGENT_POOL", [])
        if self.ua_pool:
            # Ensure the default is also present in pool for fallback
            if self.base_headers["User-Agent"] not in self.ua_pool:
                self.ua_pool.append(self.base_headers["User-Agent"])

    def get_headers(self) -> Dict[str, str]:
        headers = self.base_headers.copy()
        if self.ua_pool:
            headers["User-Agent"] = random.choice(self.ua_pool)
        return headers
