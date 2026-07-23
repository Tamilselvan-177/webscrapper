from typing import List, Dict, Any
from app.scrapers.base import BaseScraper
from app.models.filters import SearchFilters
import httpx
import os
import logging

logger = logging.getLogger(__name__)

class ReedScraper(BaseScraper):
    def __init__(self):
        super().__init__()
        self.source_name = "Reed.co.uk"
        self.api_key = os.getenv("REED_API_KEY", "01c0076f-09e5-4b02-a6f2-5b3d108a711c")
        self.base_url = "https://www.reed.co.uk/api/1.0/search"
        self.detail_url = "https://www.reed.co.uk/api/1.0/jobs/{job_id}"

    async def get_jobs(self, filters: SearchFilters, page: int = 1) -> List[Dict[str, Any]]:
        all_jobs = []
        results_to_take = 25
        results_to_skip = (page - 1) * results_to_take

        params = {
            "resultsToTake": results_to_take,
            "resultsToSkip": results_to_skip,
        }
        if filters.keyword:
            params["keywords"] = filters.keyword
        if filters.company:
            params["keywords"] = f"{params.get('keywords', '')} {filters.company}".strip()
        if filters.city:
            params["locationName"] = filters.city

        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                response = await client.get(
                    self.base_url,
                    params=params,
                    auth=(self.api_key, "")  # Reed uses API key as Basic Auth username
                )
                response.raise_for_status()
                data = response.json()
                all_jobs = data.get("results", [])
            except httpx.HTTPError as e:
                logger.error(f"[Reed] HTTP Error: {e}")
            except Exception as e:
                logger.error(f"[Reed] Unexpected error: {e}")

        return all_jobs

    async def get_job_details(self, raw_job: Dict[str, Any]) -> Dict[str, Any]:
        # The search endpoint already returns descriptions for Reed
        return raw_job

    async def normalize(self, raw_job: Dict[str, Any]) -> Dict[str, Any]:
        job_id = str(raw_job.get("jobId", ""))
        job_url = f"https://www.reed.co.uk/jobs/{raw_job.get('jobTitle', 'job').lower().replace(' ', '-')}/{job_id}"

        return {
            "id": job_id,
            "title": raw_job.get("jobTitle", ""),
            "company": raw_job.get("employerName", ""),
            "country": "United Kingdom",
            "state": None,
            "city": raw_job.get("locationName", ""),
            "remote": False,
            "employment_type": raw_job.get("jobType", None),
            "salary_min": raw_job.get("minimumSalary", None),
            "salary_max": raw_job.get("maximumSalary", None),
            "currency": "GBP",
            "job_url": raw_job.get("jobUrl", job_url),
            "apply_url": raw_job.get("jobUrl", job_url),
            "description": raw_job.get("jobDescription", ""),
            "posted_date": raw_job.get("date", ""),
            "open_time": raw_job.get("date", ""),
            "close_time": raw_job.get("expirationDate", None),
            "source": self.source_name,
            "company_logo": None,
            "applicants": raw_job.get("applications", None)
        }
