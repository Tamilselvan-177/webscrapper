from typing import List, Dict, Any
from app.scrapers.base import BaseScraper
from app.models.filters import SearchFilters
import httpx
import logging

logger = logging.getLogger(__name__)

class CareerjetScraper(BaseScraper):
    """
    CareerJet provides a free public API - no API key required.
    Docs: https://www.careerjet.com/partners/api/
    """
    def __init__(self):
        super().__init__()
        self.source_name = "CareerJet"
        self.base_url = "http://public.api.careerjet.net/search"  # CareerJet only supports HTTP, not HTTPS

    async def get_jobs(self, filters: SearchFilters, page: int = 1) -> List[Dict[str, Any]]:
        all_jobs = []
        keyword = " ".join(filter(None, [filters.keyword, filters.company]))
        location = " ".join(filter(None, [filters.city, filters.country]))

        try:
            from app.core.browser_client import BrowserClient
            import asyncio
            from bs4 import BeautifulSoup
            import urllib.parse
            
            browser_client = BrowserClient(executable_path=None)
            page_obj = await browser_client.get_page()
            
            # Use UK domain by default
            kw_encoded = urllib.parse.quote(keyword or 'developer')
            loc_encoded = urllib.parse.quote(location or '')
            
            url = f"https://www.careerjet.co.uk/jobs?s={kw_encoded}&l={loc_encoded}&p={page}"
            logger.info(f"[CareerJet] Navigating to {url}")
            
            await page_obj.goto(url, wait_until="domcontentloaded", timeout=20000)
            await asyncio.sleep(2)
            
            html = await page_obj.content()
            await browser_client.close()
            
            soup = BeautifulSoup(html, "html.parser")
            job_cards = soup.find_all("article", class_="job")
            
            for card in job_cards:
                try:
                    job_data = {}
                    link = card.find("h2").find("a") if card.find("h2") else None
                    if not link:
                        continue
                        
                    job_data["job_url"] = "https://www.careerjet.co.uk" + link.get("href", "")
                    job_data["id"] = card.get("data-job-id", "")
                    job_data["title"] = link.get_text(strip=True)
                    
                    company_elem = card.find("p", class_="company")
                    job_data["company"] = company_elem.get_text(strip=True) if company_elem else ""
                    
                    loc_elem = card.find("ul", class_="location")
                    job_data["location_raw"] = loc_elem.get_text(strip=True) if loc_elem else ""
                    
                    desc_elem = card.find("div", class_="desc")
                    job_data["description"] = desc_elem.get_text(strip=True) if desc_elem else ""
                    
                    if job_data.get("title"):
                        all_jobs.append(job_data)
                except Exception as e:
                    logger.warning(f"[CareerJet] Error parsing card: {e}")
                    continue

        except Exception as e:
            logger.error(f"[CareerJet] Browser Error: {e}")

        return all_jobs

    async def get_job_details(self, raw_job: Dict[str, Any]) -> Dict[str, Any]:
        return raw_job

    async def normalize(self, raw_job: Dict[str, Any]) -> Dict[str, Any]:
        loc_raw = raw_job.get("locations", "")
        city, country = loc_raw, None
        if "," in loc_raw:
            parts = loc_raw.split(",")
            city = parts[0].strip()
            country = parts[-1].strip()

        return {
            "id": raw_job.get("id", ""),
            "title": raw_job.get("title", ""),
            "company": raw_job.get("company", ""),
            "country": country,
            "state": None,
            "city": city,
            "remote": False,
            "employment_type": None,
            "salary_min": None,
            "salary_max": None,
            "currency": None,
            "job_url": raw_job.get("url", ""),
            "apply_url": raw_job.get("url", ""),
            "description": raw_job.get("description", ""),
            "posted_date": raw_job.get("date", ""),
            "open_time": raw_job.get("date", ""),
            "close_time": None,
            "source": self.source_name,
            "company_logo": None,
            "applicants": None
        }
