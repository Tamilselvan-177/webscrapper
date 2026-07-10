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

    async def start(self):
        import os
        self.playwright = await async_playwright().start()
        
        ws_url = os.environ.get("OBSCURA_WS_URL")
        if ws_url:
            logger.info(f"Connecting to remote browser engine at: {ws_url}")
            self.browser = await self.playwright.chromium.connect_over_cdp(ws_url)
        else:
            launch_args = {"headless": True}
            if self.executable_path:
                logger.info(f"Launching custom browser engine at: {self.executable_path}")
                launch_args["executable_path"] = self.executable_path
                
            self.browser = await self.playwright.chromium.launch(**launch_args)

    async def get_page(self) -> Page:
        if not self.browser:
            await self.start()
        return await self.browser.new_page()
        
    async def close(self):
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
