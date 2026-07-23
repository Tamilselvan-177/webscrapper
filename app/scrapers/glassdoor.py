from typing import List, Dict, Any
from app.scrapers.base import BaseScraper
from app.models.filters import SearchFilters
import httpx
import logging
from fake_useragent import UserAgent

logger = logging.getLogger(__name__)

class GlassdoorScraper(BaseScraper):
    def __init__(self):
        super().__init__()
        self.source_name = "Glassdoor"
        self.base_url = "https://www.glassdoor.com/graph"
        self.ua = UserAgent()

    async def _get_headers(self) -> dict:
        return {
            'User-Agent': self.ua.random,
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'Referer': 'https://www.glassdoor.com/Job/index.htm',
            'Origin': 'https://www.glassdoor.com',
            'gd-csrf-token': 'Ft6oHEMHy-HQKcPPLuX00A:0mg8oYElsKhfSSjHv74Vr3bRQzlw3j2gFm-HNh7gHZg1jV2xsQgWj3_Md8a15x7KLzjrB1A6Jl6'
        }

    async def get_jobs(self, filters: SearchFilters, page: int = 1) -> List[Dict[str, Any]]:
        all_jobs = []
        keyword = " ".join(filter(None, [filters.keyword, filters.company]))
        location = " ".join(filter(None, [filters.city, filters.country]))

        # Glassdoor uses a GraphQL endpoint
        payload = [{
            "operationName": "JobsSearchQuery",
            "variables": {
                "keyword": keyword or "engineer",
                "locationId": 0,
                "locationType": "C",
                "numJobsToShow": 25,
                "pageCursor": None,
                "pageNumber": page,
                "filterParams": [],
                "originalPageUrl": "https://www.glassdoor.com/Job/index.htm",
                "seoFriendlyUrlInput": "",
                "parameterUrlInput": f"KO0,{len(keyword)}.htm" if keyword else "",
                "queryString": "",
                "location": location or ""
            },
            "query": "query JobsSearchQuery($keyword: String, $location: String, $pageNumber: Int, $numJobsToShow: Int) { jobListings(contextHolder: {searchParams: {keyword: $keyword, locationStr: $location, numPerPage: $numJobsToShow, pageNumber: $pageNumber}}) { jobListings { jobview { job { jobTitleText listingId description } employer { name squareLogoUrl } jobLocation { locationName } header { ageInDays } } } } }"
        }]

        async with httpx.AsyncClient(timeout=20.0) as client:
            try:
                response = await client.post(self.base_url, json=payload, headers=await self._get_headers())
                response.raise_for_status()
                data = response.json()
                listings = data[0].get("data", {}).get("jobListings", {}).get("jobListings", [])
                all_jobs = listings
            except Exception as e:
                logger.error(f"[Glassdoor] Error: {e}")

        return all_jobs

    async def get_job_details(self, raw_job: Dict[str, Any]) -> Dict[str, Any]:
        return raw_job

    async def normalize(self, raw_job: Dict[str, Any]) -> Dict[str, Any]:
        jobview = raw_job.get("jobview", {})
        job = jobview.get("job", {})
        employer = jobview.get("employer", {})
        location_obj = jobview.get("jobLocation", {})
        header = jobview.get("header", {})

        job_id = str(job.get("listingId", ""))
        location_name = location_obj.get("locationName", "")
        city, country = location_name, None
        if "," in location_name:
            parts = location_name.split(",")
            city = parts[0].strip()
            country = parts[-1].strip()

        return {
            "id": job_id,
            "title": job.get("jobTitleText", ""),
            "company": employer.get("name", ""),
            "country": country,
            "state": None,
            "city": city,
            "remote": False,
            "employment_type": None,
            "salary_min": None,
            "salary_max": None,
            "currency": None,
            "job_url": f"https://www.glassdoor.com/job-listing/j?jl={job_id}",
            "apply_url": f"https://www.glassdoor.com/job-listing/j?jl={job_id}",
            "description": job.get("description", ""),
            "posted_date": "",
            "open_time": "",
            "close_time": None,
            "source": self.source_name,
            "company_logo": employer.get("squareLogoUrl", None),
            "applicants": None
        }
