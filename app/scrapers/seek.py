from typing import List, Dict, Any
from app.scrapers.base import BaseScraper
from app.models.filters import SearchFilters
from bs4 import BeautifulSoup
import httpx
import logging
from fake_useragent import UserAgent

logger = logging.getLogger(__name__)

class SeekScraper(BaseScraper):
    def __init__(self):
        super().__init__()
        self.source_name = "SEEK"
        self.base_url = "https://www.seek.com.au/api/chalice-search/v4/search"
        self.ua = UserAgent()

    async def _get_headers(self) -> dict:
        return {
            'User-Agent': self.ua.random,
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-AU,en;q=0.9',
            'Referer': 'https://www.seek.com.au/',
            'Origin': 'https://www.seek.com.au',
        }

    async def get_jobs(self, filters: SearchFilters, page: int = 1) -> List[Dict[str, Any]]:
        all_jobs = []
        keyword = " ".join(filter(None, [filters.keyword, filters.company]))
        location = " ".join(filter(None, [filters.city, filters.country]))

        # SEEK uses this undocumented search endpoint
        params = {
            "where": location or "All Australia",
            "keywords": keyword or "",
            "page": page,
            "pageSize": 25,
            "sortmode": "ListedDate",
        }

        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            try:
                response = await client.get(
                    "https://www.seek.com.au/api/chalice-search/v4/search",
                    params=params,
                    headers={
                        **await self._get_headers(),
                        "seek-request-site": "candidate-seek-au",
                        "seek-request-country": "AU",
                    }
                )
                if response.status_code == 404:
                    # Try alternative endpoint
                    response = await client.get(
                        "https://www.seek.com.au/jobs-api/v5/search",
                        params={"keywords": keyword, "where": location or "Australia", "page": page},
                        headers=await self._get_headers()
                    )
                response.raise_for_status()
                data = response.json()
                results = data.get("data", []) or data.get("jobs", []) or data.get("results", [])
                logger.info(f"[SEEK] Got {len(results)} jobs from API")
                all_jobs = results
            except httpx.HTTPError as e:
                logger.error(f"[SEEK] HTTP Error: {e}")
            except Exception as e:
                logger.error(f"[SEEK] Error: {e}")

        return all_jobs

    async def get_job_details(self, raw_job: Dict[str, Any]) -> Dict[str, Any]:
        return raw_job

    async def normalize(self, raw_job: Dict[str, Any]) -> Dict[str, Any]:
        job_id = str(raw_job.get("id", ""))
        location = raw_job.get("location", "") or raw_job.get("suburb", "")
        company = raw_job.get("advertiser", {})
        company_name = company.get("description", "") if isinstance(company, dict) else str(company)

        salary = raw_job.get("salary", "")

        return {
            "id": job_id,
            "title": raw_job.get("title", ""),
            "company": company_name,
            "country": "Australia",
            "state": raw_job.get("area", None),
            "city": location,
            "remote": "remote" in raw_job.get("workType", "").lower(),
            "employment_type": raw_job.get("workType", None),
            "salary_min": None,
            "salary_max": None,
            "currency": "AUD",
            "job_url": f"https://www.seek.com.au/job/{job_id}",
            "apply_url": f"https://www.seek.com.au/job/{job_id}",
            "description": raw_job.get("teaser", ""),
            "posted_date": raw_job.get("listingDate", ""),
            "open_time": raw_job.get("listingDate", ""),
            "close_time": None,
            "source": self.source_name,
            "company_logo": raw_job.get("companyProfileStructuredDataId", None),
            "applicants": None
        }
