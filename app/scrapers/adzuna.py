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
        if not self.app_id or not self.app_key:
            return all_jobs

        # Adzuna requires a country code. If city/country provided, we try to guess, but default to 'ae' (UAE/Dubai) or 'gb'
        # Adzuna supported codes: gb, us, au, br, ca, fr, de, in, it, nl, nz, pl, ru, sg, za, at, ae
        country_code = "gb" # Default to UK
        
        location_raw = ""
        if filters.city:
            location_raw += filters.city.lower()
        if filters.country:
            location_raw += " " + filters.country.lower()
            
        if "dubai" in location_raw or "ae" in location_raw or "emirates" in location_raw:
            country_code = "ae"
        elif "india" in location_raw:
            country_code = "in"
        elif "us" in location_raw or "america" in location_raw:
            country_code = "us"

        keyword = filters.keyword or ""
        if filters.company:
            keyword += f" {filters.company}"
            
        where = filters.city or ""

        url = f"https://api.adzuna.com/v1/api/jobs/{country_code}/search/{page}"
        params = {
            "app_id": self.app_id,
            "app_key": self.app_key,
            "results_per_page": 25,
            "what": keyword.strip(),
            "where": where
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
                
                results = data.get("results", [])
                for raw_job in results:
                    all_jobs.append(raw_job)
                    
            except httpx.HTTPError as e:
                logger.error(f"[Adzuna] HTTP Error: {e}")
            except Exception as e:
                logger.error(f"[Adzuna] Unexpected error: {e}")

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
