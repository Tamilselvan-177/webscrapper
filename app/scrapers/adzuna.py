from typing import List, Dict, Any
from app.scrapers.base import BaseScraper
from app.models.filters import SearchFilters
import httpx
import os
import logging
import urllib.parse

logger = logging.getLogger(__name__)

class AdzunaScraper(BaseScraper):
    def __init__(self):
        super().__init__()
        self.source_name = "Adzuna"
        # Reading API keys from environment
        self.app_id = os.getenv("ADZUNA_APP_ID")
        self.app_key = os.getenv("ADZUNA_APP_KEY")
        
        if not self.app_id or not self.app_key:
            logger.error("Adzuna API credentials (ADZUNA_APP_ID / ADZUNA_APP_KEY) are missing in environment variables.")

    async def get_jobs(self, filters: SearchFilters, page: int = 1) -> List[Dict[str, Any]]:
        all_jobs = []
        try:
            from app.core.browser_client import BrowserClient
            import asyncio
            from bs4 import BeautifulSoup
            import urllib.parse
            
            browser_client = BrowserClient(executable_path=None)
            page_obj = await browser_client.get_page()
            
            kw_encoded = urllib.parse.quote(filters.keyword or 'developer')
            loc_encoded = urllib.parse.quote(filters.city or 'US')
            
            url = f"https://www.adzuna.com/search?q={kw_encoded}&w={loc_encoded}"
            logger.info(f"[Adzuna] Navigating to {url}")
            
            await page_obj.goto(url, wait_until="domcontentloaded", timeout=20000)
            await asyncio.sleep(2)
            
            html = await page_obj.content()
            await browser_client.close()
            
            soup = BeautifulSoup(html, "html.parser")
            job_cards = soup.find_all("div", attrs={"data-aid": True})
            
            for card in job_cards:
                try:
                    job_data = {}
                    link = card.find("h2").find("a") if card.find("h2") else card.find("a")
                    if not link:
                        continue
                        
                    job_data["job_url"] = link.get("href", "")
                    job_data["id"] = card.get("data-aid", "")
                    job_data["title"] = link.get_text(strip=True)
                    
                    company_elem = card.find("div", class_="ui-company")
                    job_data["company"] = company_elem.get_text(strip=True) if company_elem else ""
                    
                    loc_elem = card.find("div", class_="ui-location")
                    job_data["location_raw"] = loc_elem.get_text(strip=True) if loc_elem else ""
                    
                    desc_elem = card.find("span", attrs={"data-aid": "job-snippet"})
                    job_data["description"] = desc_elem.get_text(strip=True) if desc_elem else ""
                    
                    if job_data.get("title"):
                        all_jobs.append(job_data)
                except Exception as e:
                    logger.warning(f"[Adzuna] Error parsing card: {e}")
                    continue

        except Exception as e:
            logger.error(f"[Adzuna] Browser Error: {e}")

        return all_jobs

    async def get_job_details(self, raw_job: Dict[str, Any]) -> Dict[str, Any]:
        # Adzuna provides description in the initial payload
        return raw_job

    async def normalize(self, raw_job: Dict[str, Any]) -> Dict[str, Any]:
        company_obj = raw_job.get("company", {})
        company_name = company_obj.get("display_name", "")
        
        location_obj = raw_job.get("location", {})
        area = location_obj.get("display_name", "")

        return {
            "id": str(raw_job.get("id", "")),
            "title": raw_job.get("title", ""),
            "company": company_name,
            "country": None,
            "state": None,
            "city": area,
            "remote": False,
            "employment_type": raw_job.get("contract_time", None) or raw_job.get("contract_type", None),
            "salary_min": raw_job.get("salary_min", None),
            "salary_max": raw_job.get("salary_max", None),
            "currency": None,
            "job_url": raw_job.get("redirect_url", ""),
            "apply_url": raw_job.get("redirect_url", ""),
            "description": raw_job.get("description", ""),
            "posted_date": raw_job.get("created", "").split("T")[0] if raw_job.get("created") else "",
            "open_time": raw_job.get("created", ""),
            "close_time": None,
            "source": self.source_name,
            "company_logo": None,
            "applicants": None
        }
