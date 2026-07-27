"""
Proxy-aware HTTP client with residential proxy rotation and anti-detection.

Supports:
- Environment-variable-based proxy configuration
- Multiple proxy provider formats (Bright Data, Oxylabs, Smartproxy, custom)
- Automatic proxy rotation per request
- Realistic browser fingerprint headers
- Retry with exponential backoff

Environment variables:
    PROXY_URL          - Single proxy URL (http://user:pass@host:port)
    PROXY_URLS         - Comma-separated list of proxy URLs for rotation
    PROXY_PROVIDER    - Provider name: "brightdata", "oxylabs", "smartproxy", "custom"
    PROXY_USERNAME     - Proxy auth username (used with PROXY_PROVIDER)
    PROXY_PASSWORD     - Proxy auth password (used with PROXY_PROVIDER)
    PROXY_HOST         - Proxy host (used with PROXY_PROVIDER)
    PROXY_PORT         - Proxy port (used with PROXY_PROVIDER)
    USE_PROXIES        - "true" to enable proxy usage, "false" to disable (default)
    PROXY_COUNTRY      - Country code for geo-targeted proxies (default: "gb")
"""

import os
import random
import itertools
import logging
from typing import Optional, List, Dict, Any
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from fake_useragent import UserAgent

logger = logging.getLogger(__name__)

# Realistic browser fingerprint headers
BROWSER_FINGERPRINTS = [
    {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Language": "en-GB,en-US;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Sec-CH-UA": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        "Sec-CH-UA-Mobile": "?0",
        "Sec-CH-UA-Platform": '"Windows"',
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
        "Connection": "keep-alive",
    },
    {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-GB,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Sec-CH-UA": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        "Sec-CH-UA-Mobile": "?0",
        "Sec-CH-UA-Platform": '"macOS"',
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
        "Connection": "keep-alive",
    },
    {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Sec-CH-UA": '"Chromium";v="130", "Google Chrome";v="130", "Not?A_Brand";v="99"',
        "Sec-CH-UA-Mobile": "?0",
        "Sec-CH-UA-Platform": '"Windows"',
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
        "Connection": "keep-alive",
    },
]


def _build_proxy_url(provider: str, username: str, password: str, host: str, port: str, country: str = "gb") -> str:
    if provider == "brightdata":
        return f"http://{username}-country-{country}:password@{host}:{port}"
    elif provider == "oxylabs":
        return f"http://{username}-country-{country}:password@{host}:{port}"
    else:
        return f"http://{username}:{password}@{host}:{port}"


def _get_proxy_urls() -> List[str]:
    urls = []
    single = os.environ.get("PROXY_URL", "").strip()
    if single:
        urls.append(single)
    multi = os.environ.get("PROXY_URLS", "").strip()
    if multi:
        urls.extend([u.strip() for u in multi.split(",") if u.strip()])
    provider = os.environ.get("PROXY_PROVIDER", "").strip().lower()
    if provider:
        username = os.environ.get("PROXY_USERNAME", "")
        password = os.environ.get("PROXY_PASSWORD", "")
        host = os.environ.get("PROXY_HOST", "")
        port = os.environ.get("PROXY_PORT", "")
        country = os.environ.get("PROXY_COUNTRY", "gb")
        if username and password and host and port:
            urls.append(_build_proxy_url(provider, username, password, host, port, country))
    return urls


class ProxyHTTPClient:
    def __init__(self, timeout: float = 15.0, max_retries: int = 3, use_proxy: Optional[bool] = None):
        self.ua = UserAgent()
        self.timeout = timeout
        self.max_retries = max_retries
        if use_proxy is None:
            use_proxy = os.environ.get("USE_PROXIES", "false").lower() == "true"
        self.use_proxy = use_proxy
        self._proxy_urls = _get_proxy_urls()
        self._proxy_cycle = itertools.cycle(self._proxy_urls) if self._proxy_urls else None
        if self.use_proxy and not self._proxy_urls:
            logger.warning("USE_PROXIES=true but no proxies configured. Running without proxies.")
            self.use_proxy = False

    def _next_proxy(self) -> Optional[str]:
        if self._proxy_cycle:
            return next(self._proxy_cycle)
        return None

    def _get_fingerprint(self) -> Dict[str, str]:
        fp = random.choice(BROWSER_FINGERPRINTS).copy()
        fp["User-Agent"] = self.ua.random
        return fp

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.RequestError,)),
        reraise=True,
    )
    async def get(self, url: str, params: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None) -> httpx.Response:
        req_headers = self._get_fingerprint()
        if headers:
            req_headers.update(headers)

        proxy_url = self._next_proxy() if self.use_proxy else None

        client_kwargs: Dict[str, Any] = {
            "timeout": httpx.Timeout(self.timeout),
            "follow_redirects": True,
            "verify": False,
        }
        if proxy_url:
            client_kwargs["proxy"] = proxy_url

        async with httpx.AsyncClient(**client_kwargs) as client:
            response = await client.get(url, params=params, headers=req_headers)
            return response

    async def close(self):
        pass
