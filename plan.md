# Plan to Reduce `get_website` Access Denials

## 1. Problem Summary
Many target sites return **403 Forbidden** when `get_website` fetches them. The current implementation:
- Uses a single static `User‑Agent` (set on the `httpx.AsyncClient`).
- Sends no additional headers (Accept, Accept‑Language, Referer, etc.).
- Does not respect `robots.txt` or site‑specific crawl policies.
- Lacks retry logic with header variation or proxy fallback.
- Handles only plain HTTP(S) requests; sites that require JavaScript rendering or Cloudflare challenges are never retried with a browser.

These factors trigger anti‑bot/anti‑scraping defenses, resulting in 403 errors.

## 2. Design Goals
1. **Higher success rate** for a wide range of public sites.
2. **Graceful degradation** – fallback strategies before reporting an error.
3. **Configurable** – allow operators to tune aggressiveness without code changes.
4. **Minimal impact** on existing cache/rate‑limiter logic.
5. **Observability** – emit detailed events for each fallback step.

## 3. Proposed Architectural Changes
### 3.1 Header Management Layer
- Introduce a `HeaderBuilder` class responsible for constructing request headers.
- Configuration (`Tools.Valves`) will expose:
  - `DEFAULT_USER_AGENT` (string, default existing value).
  - `USER_AGENT_POOL` (list of strings) – optional rotation.
  - `EXTRA_HEADERS` (dict) – static additional headers (Accept, Accept‑Language, etc.).
- `HeaderBuilder.get_headers()` returns a dict; if a pool is defined it randomly picks one per request.
- Update `_get_website_content_cached` to use `self.client.get(url, headers=HeaderBuilder.get_headers(), timeout=120)`.

### 3.2 Retry & Fallback Strategy
Create a `FetchStrategy` helper with the following steps:
1. **Primary HTTP fetch** – as above.
2. **Retry with altered headers** – up to `FETCH_RETRY_COUNT` (default 2) using a different User‑Agent from the pool.
3. **Proxy fallback** – if `PROXY_LIST` is configured, retry the request through a randomly chosen proxy.
4. **Headless browser fallback** – use `playwright.async_api` (or `pyppeteer`) to render the page when HTTP fetch still fails with 403/4xx/5xx.
5. **Final error** – if all steps fail, propagate a `WebScrapingError` with a detailed message.

Configuration variables:
- `FETCH_RETRY_COUNT`
- `PROXY_LIST` (list of `http://host:port` strings)
- `BROWSER_TIMEOUT_SECONDS`
- `BROWSER_USER_AGENT` (optional, defaults to pool entry)

### 3.3 robots.txt Respect
- Add a lightweight `RobotsChecker` that, on the first request per domain, fetches `https://{domain}/robots.txt` (cached per domain).
- Use `robots.txt` rules to decide if the path is allowed for the chosen User‑Agent.
- If disallowed, emit a warning event and skip fetch, returning a cached result if available or a clear error.
- Config flag `RESPECT_ROBOTS_TXT` (default `True`).

### 3.4 Event Enhancements
Emit new event types via `self.emitter`:
- `fetch_attempt` – includes attempt number, headers used, proxy (if any).
- `robots_blocked` – when robots.txt denies access.
- `browser_fallback` – when switching to headless rendering.
- `fetch_success` – final successful method.

These events give the client visibility into why a request succeeded or failed.

## 4. Implementation Steps
| Step | File(s) | Action |
|------|---------|--------|
| 1 | `tools/valves.py` (or equivalent config module) | Add new config fields (`DEFAULT_USER_AGENT`, `USER_AGENT_POOL`, `EXTRA_HEADERS`, `FETCH_RETRY_COUNT`, `PROXY_LIST`, `BROWSER_TIMEOUT_SECONDS`, `RESPECT_ROBOTS_TXT`). |
| 2 | `utils/header_builder.py` (new) | Implement `HeaderBuilder` with random pool selection and merging of `EXTRA_HEADERS`.
| 3 | `utils/fetch_strategy.py` (new) | Implement `FetchStrategy.fetch(url)` orchestrating the steps above, using `HeaderBuilder`, `httpx.AsyncClient`, optional proxy support, and fallback to Playwright.
| 4 | `utils/robots_checker.py` (new) | Cache and parse robots.txt using `reppy.robots.Robots`. Provide `is_allowed(url, user_agent)`.
| 5 | `mcp_server.py` (or the module containing `_get_website_content_cached`) | Replace direct `self.client.get` call with `await FetchStrategy.fetch(url)`.
| 6 | `mcp_server.py` | Adjust error handling to capture `FetchError` subclasses and emit the new events.
| 7 | `event_emitter.py` (or wherever `self.emitter` is defined) | Add new event types (`fetch_attempt`, `robots_blocked`, `browser_fallback`).
| 8 | Tests | Add unit tests for `HeaderBuilder` randomness, `FetchStrategy` retry logic (mock httpx responses), `RobotsChecker` allow/deny cases, and successful browser fallback (mock Playwright).
| 9 | Documentation | Update `get_website_architecture.md` to reflect new components.
|10| CI/Deployment | Ensure new dependencies (`playwright`, `reppy`) are added to `requirements.txt` and installed in CI.

## 5. Testing & Validation
1. **Unit Tests** – cover each helper in isolation with mocked network responses.
2. **Integration Tests** – run `get_website` against a curated list of sites known to require different headers or JavaScript rendering (e.g., `https://example.com`, a Cloudflare‑protected page, a site that blocks generic User‑Agents).
3. **Metrics** – add a simple counter in the emitter to track how many requests succeed on primary HTTP vs. fallback methods.
4. **Performance** – benchmark the added latency; ensure fallback steps are only invoked when necessary.
5. **Cache Compatibility** – verify that cached entries remain valid after header changes (cache key stays URL‑only).

## 6. Rollout Plan
1. **Feature flag** – introduce `ENABLE_ADVANCED_FETCH` (default `False`). Deploy code with flag off; existing behavior unchanged.
2. **Canary** – enable flag for a small subset of requests (e.g., 5 % of domains) and monitor success rate and latency.
3. **Full Enable** – once metrics show > 90 % reduction in 403 errors and acceptable latency (< 2 s extra on average), flip flag to `True` for all requests.
4. **Monitoring** – alert on spikes in `fetch_error` events or high fallback usage, indicating possible new anti‑scraping measures.

## 7. Risks & Mitigations
| Risk | Impact | Mitigation |
|------|--------|------------|
| Increased latency due to retries/fallbacks | User‑perceived slowdown | Use feature flag; limit retries; cache robots.txt results.
| Proxy misconfiguration causing request failures | Lower success rate | Validate proxy list at startup; fallback to direct request.
| Headless browser adds heavy dependency | CI/CD complexity | Make Playwright optional; only import when needed.
| Over‑caching of robots.txt leading to stale rules | Unexpected blocks | Set reasonable `ROBOTS_TTL_SECONDS` (e.g., 24 h).
| Random User‑Agent may violate target site policies | Potential legal/terms issues | Keep pool to common browser agents; allow operator to customize.

---

*Prepared by the refactoring lead after reviewing `get_website_architecture.md`. All changes should be reflected in the repository's documentation and CI pipeline.*