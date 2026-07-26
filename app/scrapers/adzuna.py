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
        # Reading API keys from environment (defaulting to working test keys if not set)
        self.app_id = os.getenv("ADZUNA_APP_ID", "71b0f298")
        self.app_key = os.getenv("ADZUNA_APP_KEY", "8f2ce8aef294190f8892004471d453d4")
        
        if not self.app_id or not self.app_key:
            logger.error("Adzuna API credentials (ADZUNA_APP_ID / ADZUNA_APP_KEY) are missing in environment variables.")

    async def get_jobs(self, filters: SearchFilters, page: int = 1) -> List[Dict[str, Any]]:
        all_jobs = []
        try:
            country = (filters.country or "gb").lower().replace("uk", "gb").replace("united kingdom", "gb").replace("germany", "de").replace("australia", "au").replace("canada", "ca").replace("usa", "us").replace("united states", "us")
            if country not in ["gb", "us", "de", "fr", "au", "ca", "nl", "it", "es", "pl", "in", "br", "at", "ch", "ru", "za", "nz"]:
                country = "gb"

            keyword = urllib.parse.quote(filters.keyword or filters.company or "developer")
            location = urllib.parse.quote(filters.city or "")
            
            url = f"https://api.adzuna.com/v1/api/jobs/{country}/search/{page}?app_id={self.app_id}&app_key={self.app_key}&what={keyword}&results_per_page=20"
            if location:
                url += f"&where={location}"

            logger.info(f"[Adzuna] Fetching from API: {url}")
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    all_jobs = data.get("results", [])
                else:
                    logger.warning(f"[Adzuna] API returned status {resp.status_code}: {resp.text}")
        except Exception as e:
            logger.error(f"[Adzuna] API Error: {e}")

        return all_jobs

    async def get_job_details(self, raw_job: Dict[str, Any]) -> Dict[str, Any]:
        # Adzuna provides description in the initial payload
        return raw_job

    async def normalize(self, raw_job: Dict[str, Any]) -> Dict[str, Any]:
        company_obj = raw_job.get("company", {})
        company_name = company_obj.get("display_name", "") if isinstance(company_obj, dict) else str(company_obj)
        
        location_obj = raw_job.get("location", {})
        area = location_obj.get("display_name", "") if isinstance(location_obj, dict) else str(location_obj)

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
