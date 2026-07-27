"""
Anti-detect browser client using Playwright with stealth evasions.

Features:
- Playwright stealth plugin for anti-bot bypass
- Randomized browser fingerprints (UA, viewport, locale, timezone)
- Proxy support via Playwright's built-in proxy parameter
- Cloudflare Turnstile challenge detection and wait
- Akamai challenge detection and wait
- Realistic mouse movements and scroll behavior

Environment variables:
    PROXY_URL / PROXY_URLS / PROXY_PROVIDER - Same as proxy_client.py
    BROWSER_HEADLESS - "true" (default) or "false" for visible browser
    BROWSER_TIMEOUT  - Navigation timeout in ms (default: 30000)
"""

import os
import random
import asyncio
import logging
from typing import Optional, List, Dict, Any, Tuple
from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Playwright

logger = logging.getLogger(__name__)

# Browser fingerprint configurations
BROWSER_CONFIGS = [
    {
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "viewport": {"width": 1920, "height": 1080},
        "locale": "en-GB",
        "timezone_id": "Europe/London",
        "color_scheme": "light",
    },
    {
        "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "viewport": {"width": 1440, "height": 900},
        "locale": "en-GB",
        "timezone_id": "Europe/London",
        "color_scheme": "light",
    },
    {
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
        "viewport": {"width": 1366, "height": 768},
        "locale": "en-US",
        "timezone_id": "America/New_York",
        "color_scheme": "light",
    },
    {
        "user_agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "viewport": {"width": 1920, "height": 1080},
        "locale": "en-GB",
        "timezone_id": "Europe/London",
        "color_scheme": "light",
    },
]

# German-specific configs for StepStone
GERMAN_BROWSER_CONFIGS = [
    {
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "viewport": {"width": 1920, "height": 1080},
        "locale": "de-DE",
        "timezone_id": "Europe/Berlin",
        "color_scheme": "light",
    },
    {
        "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "viewport": {"width": 1440, "height": 900},
        "locale": "de-DE",
        "timezone_id": "Europe/Berlin",
        "color_scheme": "light",
    },
]

# Cloudflare Turnstile detection markers
CF_MARKERS = ["just a moment", "cf-turnstile", "checking your browser", "__cf_chl", "cloudflare"]
AKAMAI_MARKERS = ["access denied", "ak_bmsc", "reference #", "bm-verify", "akamai"]


def _get_proxy_url() -> Optional[str]:
    """Get proxy URL from environment (same logic as proxy_client.py)."""
    single = os.environ.get("PROXY_URL", "").strip()
    if single:
        return single

    multi = os.environ.get("PROXY_URLS", "").strip()
    if multi:
        urls = [u.strip() for u in multi.split(",") if u.strip()]
        return random.choice(urls) if urls else None

    provider = os.environ.get("PROXY_PROVIDER", "").strip().lower()
    if provider:
        username = os.environ.get("PROXY_USERNAME", "")
        password = os.environ.get("PROXY_PASSWORD", "")
        host = os.environ.get("PROXY_HOST", "")
        port = os.environ.get("PROXY_PORT", "")
        country = os.environ.get("PROXY_COUNTRY", "gb")
        if username and password and host and port:
            if provider == "brightdata":
                return f"http://{username}-country-{country}:password@{host}:{port}"
            elif provider == "oxylabs":
                return f"http://{username}-country-{country}:password@{host}:{port}"
            else:
                return f"http://{username}:{password}@{host}:{port}"

    return None


def _detect_challenge(html: str) -> Optional[str]:
    """Detect if the page contains a bot challenge."""
    lower = html.lower()[:5000]
    for marker in CF_MARKERS:
        if marker in lower:
            return "cloudflare"
    for marker in AKAMAI_MARKERS:
        if marker in lower:
            return "akamai"
    return None


def _random_sleep(min_s: float = 1.0, max_s: float = 3.0):
    """Return a random sleep duration."""
    return random.uniform(min_s, max_s)


class AntiDetectBrowser:
    """
    Anti-detect Playwright browser with stealth evasions.

    Usage:
        async with AntiDetectBrowser(locale="en-GB") as browser:
            page = await browser.new_page()
            await page.goto(url)
            html = await page.content()
    """

    def __init__(
        self,
        headless: Optional[bool] = None,
        proxy: Optional[str] = None,
        locale: str = "en-GB",
        timeout: int = 30000,
    ):
        self.headless = headless if headless is not None else os.environ.get("BROWSER_HEADLESS", "true").lower() == "true"
        self.proxy = proxy or _get_proxy_url()
        self.locale = locale
        self.timeout = timeout

        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None

        # Select appropriate fingerprint configs
        if locale.startswith("de"):
            self._configs = GERMAN_BROWSER_CONFIGS
        else:
            self._configs = BROWSER_CONFIGS

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, *args):
        await self.close()

    async def start(self):
        """Launch the browser."""
        self._playwright = await async_playwright().start()

        launch_args = {
            "headless": self.headless,
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-accelerated-2d-canvas",
                "--no-first-run",
                "--no-zygote",
                "--disable-gpu",
                "--disable-web-security",
                "--disable-features=VizDisplayCompositor",
                "--window-size=1920,1080",
            ],
        }

        if self.proxy:
            launch_args["proxy"] = {"server": self.proxy}
            logger.info(f"Browser launching with proxy: {self.proxy[:30]}...")

        self._browser = await self._playwright.chromium.launch(**launch_args)

    async def new_page(self) -> Page:
        """Create a new page with randomized fingerprint."""
        config = random.choice(self._configs)

        context_args = {
            "viewport": config["viewport"],
            "user_agent": config["user_agent"],
            "locale": config["locale"],
            "timezone_id": config["timezone_id"],
            "color_scheme": config["color_scheme"],
            "java_script_enabled": True,
            "bypass_csp": False,
            "ignore_https_errors": True,
        }

        context = await self._browser.new_context(**context_args)

        # Apply stealth evasions
        page = await context.new_page()
        await self._apply_stealth(page)

        page.set_default_timeout(self.timeout)
        return page

    async def _apply_stealth(self, page: Page):
        """Apply anti-detection stealth patches to a page."""
        # Override navigator.webdriver
        await page.add_init_script("""
            // Remove webdriver property
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
            });

            // Override navigator.plugins
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5],
            });

            // Override navigator.languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-GB', 'en-US', 'en'],
            });

            // Override chrome property
            window.chrome = {
                runtime: {},
                loadTimes: function() {},
                csi: function() {},
                app: {},
            };

            // Override permissions
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) =>
                parameters.name === 'notifications'
                    ? Promise.resolve({ state: Notification.permission })
                    : originalQuery(parameters);

            // Override WebGL vendor and renderer
            const getParameter = WebGLRenderingContext.prototype.getParameter;
            WebGLRenderingContext.prototype.getParameter = function(parameter) {
                if (parameter === 37445) {
                    return 'Intel Inc.';
                }
                if (parameter === 37446) {
                    return 'Intel Iris OpenGL Engine';
                }
                return getParameter.apply(this, arguments);
            };

            // Override console.debug to prevent detection
            const originalDebug = console.debug;
            console.debug = function() {
                return originalDebug.apply(this, arguments);
            };

            // Override toString to prevent detection
            const originalToString = Function.prototype.toString;
            Function.prototype.toString = function() {
                if (this === Function.prototype.toString) {
                    return 'function toString() { [native code] }';
                }
                return originalToString.apply(this, arguments);
            };
        """)

    async def wait_for_cloudflare(self, page: Page, max_wait: int = 30) -> bool:
        """
        Wait for Cloudflare Turnstile challenge to resolve.
        Returns True if challenge resolved, False if timeout.
        """
        logger.info(f"[Browser] Waiting for Cloudflare challenge (max {max_wait}s)...")
        start = asyncio.get_event_loop().time()

        while (asyncio.get_event_loop().time() - start) < max_wait:
            try:
                html = await page.content()
                challenge = _detect_challenge(html)
                if challenge != "cloudflare":
                    logger.info("[Browser] Cloudflare challenge resolved")
                    return True

                # Try to interact with Turnstile checkbox if present
                try:
                    turnstile = page.frame_locator("iframe[src*='challenges.cloudflare.com']")
                    checkbox = turnstile.locator("input[type='checkbox'], .cb-i, #cf-turnstile-response")
                    if await checkbox.count() > 0:
                        await checkbox.first.click(timeout=2000)
                        logger.info("[Browser] Clicked Cloudflare Turnstile checkbox")
                except Exception:
                    pass

                await asyncio.sleep(2)
            except Exception:
                await asyncio.sleep(1)

        logger.warning("[Browser] Cloudflare challenge did not resolve in time")
        return False

    async def wait_for_akamai(self, page: Page, max_wait: int = 20) -> bool:
        """
        Wait for Akamai challenge to resolve.
        Returns True if challenge resolved, False if timeout.
        """
        logger.info(f"[Browser] Waiting for Akamai challenge (max {max_wait}s)...")
        start = asyncio.get_event_loop().time()

        while (asyncio.get_event_loop().time() - start) < max_wait:
            try:
                html = await page.content()
                challenge = _detect_challenge(html)
                if challenge != "akamai":
                    logger.info("[Browser] Akamai challenge resolved")
                    return True
                await asyncio.sleep(2)
            except Exception:
                await asyncio.sleep(1)

        logger.warning("[Browser] Akamai challenge did not resolve in time")
        return False

    async def fetch_page(
        self,
        url: str,
        wait_until: str = "domcontentloaded",
        challenge_wait: int = 30,
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Navigate to a URL and return (html, challenge_type).

        If a bot challenge is detected, waits for it to resolve.
        Returns the final HTML content and the detected challenge type (or None).
        """
        page = await self.new_page()

        try:
            # Add small random delay before navigation
            await asyncio.sleep(_random_sleep(0.5, 1.5))

            response = await page.goto(url, wait_until=wait_until, timeout=self.timeout)

            if response and response.status in (403, 429, 503):
                logger.warning(f"[Browser] Got HTTP {response.status} from {url}")

            # Check for bot challenges
            await asyncio.sleep(2)
            html = await page.content()
            challenge = _detect_challenge(html)

            if challenge == "cloudflare":
                resolved = await self.wait_for_cloudflare(page, max_wait=challenge_wait)
                if resolved:
                    await asyncio.sleep(_random_sleep(1, 3))
                    html = await page.content()
                    challenge = None
            elif challenge == "akamai":
                resolved = await self.wait_for_akamai(page, max_wait=challenge_wait)
                if resolved:
                    await asyncio.sleep(_random_sleep(1, 3))
                    html = await page.content()
                    challenge = None

            # Scroll down to trigger lazy-loaded content
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight / 3)")
            await asyncio.sleep(_random_sleep(1, 2))

            return html, challenge

        except Exception as e:
            logger.error(f"[Browser] Error fetching {url}: {e}")
            return None, "error"
        finally:
            try:
                await page.close()
            except Exception:
                pass

    async def close(self):
        """Close the browser and cleanup."""
        if self._browser:
            try:
                await self._browser.close()
            except Exception:
                pass
        if self._playwright:
            try:
                await self._playwright.stop()
            except Exception:
                pass
