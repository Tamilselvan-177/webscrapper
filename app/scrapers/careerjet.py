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
        self.base_url = "http://public.api.careerjet.net/search"

    async def get_jobs(self, filters: SearchFilters, page: int = 1) -> List[Dict[str, Any]]:
        all_jobs = []
        keyword = " ".join(filter(None, [filters.keyword, filters.company]))
        location = " ".join(filter(None, [filters.city, filters.country]))

        # CareerJet public API - v2 endpoint
        params = {
            "locale_code": "en_GB",
            "keywords": keyword or "developer",
            "location": location or "",
            "pagesize": 20,
            "page": page,
            "sort": "date",
            "affid": "careejet_public_api",
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                response = await client.get(
                    "https://public.api.careerjet.net/search",
                    params=params,
                    headers={"User-Agent": "Mozilla/5.0 JobScraper/1.0"}
                )
                response.raise_for_status()
                data = response.json()
                jobs = data.get("jobs", [])
                logger.info(f"[CareerJet] Found {len(jobs)} jobs, type={data.get('type')}, hits={data.get('hits')}")
                all_jobs = jobs
            except httpx.HTTPError as e:
                logger.error(f"[CareerJet] HTTP Error: {e}")
            except Exception as e:
                logger.error(f"[CareerJet] Error: {e}")

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
