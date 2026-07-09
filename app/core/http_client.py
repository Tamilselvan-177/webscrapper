import httpx
import logging
from typing import Optional, Dict, Any
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from fake_useragent import UserAgent

logger = logging.getLogger(__name__)

class HTTPClient:
    def __init__(self, base_url: str = "", headers: Optional[Dict[str, str]] = None, timeout: float = 15.0):
        self.ua = UserAgent()
        
        default_headers = {
            "User-Agent": self.ua.random,
            "Accept": "application/json",
        }
        if headers:
            default_headers.update(headers)
            
        self.client = httpx.AsyncClient(
            base_url=base_url,
            headers=default_headers,
            timeout=httpx.Timeout(timeout),
            follow_redirects=True
        )

    # Retry on specific HTTP errors (429, 500, 502, 503, 504) or connection timeouts
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.RequestError)),
        reraise=True
    )
    async def get(self, url: str, params: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None) -> httpx.Response:
        req_headers = headers or {}
        # Randomize UA per request for resilience
        req_headers["User-Agent"] = self.ua.random
        
        try:
            response = await self.client.get(url, params=params, headers=req_headers)
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as e:
            if e.response.status_code in [429, 500, 502, 503, 504]:
                logger.warning(f"Retrying due to {e.response.status_code} on {url}")
                raise e
            # Don't retry for 404, 401, 403, etc.
            raise e
        except httpx.RequestError as e:
            logger.warning(f"Retrying due to connection error: {e}")
            raise e
            
    async def close(self):
        await self.client.aclose()
