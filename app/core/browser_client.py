from playwright.async_api import async_playwright, Browser, Page
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class BrowserClient:
    def __init__(self, executable_path: Optional[str] = None):
        """
        Initialize with an optional path to a custom browser executable (e.g. Obscura).
        """
        self.executable_path = executable_path
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.stealth = None

    async def start(self):
        import os
        
        # Try to set up stealth
        try:
            from playwright_stealth import Stealth
            self.stealth = Stealth()
        except ImportError:
            logger.warning("playwright-stealth not installed. Anti-bot bypass may fail.")
        
        self.playwright = await async_playwright().start()
        
        ws_url = os.environ.get("OBSCURA_WS_URL")
        if ws_url:
            logger.info(f"Connecting to remote browser engine at: {ws_url}")
            self.browser = await self.playwright.chromium.connect_over_cdp(ws_url)
        else:
            launch_args = {
                "headless": True,
                "args": [
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                ]
            }
            if self.executable_path:
                logger.info(f"Launching custom browser engine at: {self.executable_path}")
                launch_args["executable_path"] = self.executable_path
                
            self.browser = await self.playwright.chromium.launch(**launch_args)

    async def get_page(self) -> Page:
        if not self.browser:
            await self.start()
        
        # Create a realistic browser context
        context = await self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            locale='en-US',
        )
        
        page = await context.new_page()
        
        # Apply stealth evasions
        if self.stealth:
            try:
                await self.stealth.apply_stealth_async(page)
                logger.info("Stealth evasions applied successfully")
            except Exception as e:
                logger.warning(f"Failed to apply stealth: {e}")
        
        return page
        
    async def close(self):
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

