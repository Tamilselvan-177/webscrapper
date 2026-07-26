from typing import List, Dict, Any
from app.scrapers.base import BaseScraper
from app.models.filters import SearchFilters
from app.core.http_client import HTTPClient
from bs4 import BeautifulSoup

class AshbyScraper(BaseScraper):
    def __init__(self):
        super().__init__()
        self.source_name = "Ashby"
        self.base_url = "https://api.ashbyhq.com/posting-api/job-board"
        self.client = HTTPClient(base_url=self.base_url)

    async def get_jobs(self, filters: SearchFilters, page: int = 1) -> List[Dict[str, Any]]:
        company = filters.company.lower() if filters.company else "ashby"
        self.current_company = company 
        
        url = f"/{company}"
        try:
            response = await self.client.get(url)
            data = response.json()
            raw_jobs = data.get("jobs", [])
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"[Ashby] Error fetching jobs for '{company}': {e}")
            return []
        
        # Local filtering
        filtered_jobs = []
        for job in raw_jobs:
            if filters.keyword:
                kw = filters.keyword.lower()
                title = job.get("title", "").lower()
                if kw not in title:
                    continue
            filtered_jobs.append(job)
            
        return filtered_jobs

    async def get_job_details(self, raw_job: Dict[str, Any]) -> Dict[str, Any]:
        # Ashby's posting-api endpoint already returns full descriptionHtml and descriptionPlain
        return raw_job

    async def normalize(self, raw_job: Dict[str, Any]) -> Dict[str, Any]:
        location = raw_job.get("location", "")
        # Ashby sometimes returns location object or string
        if isinstance(location, dict):
            location_str = location.get("address", {}).get("addressLocality", "")
            country = location.get("address", {}).get("addressCountry", "")
        else:
            location_str = str(location)
            country = None
            
        desc_html = raw_job.get("descriptionHtml", "")
        if desc_html:
            # Clean HTML slightly
            soup = BeautifulSoup(desc_html, "html.parser")
            for script in soup(["script", "style"]):
                script.decompose()
            clean_desc = str(soup)
        else:
            clean_desc = ""

        return {
            "id": raw_job.get("id", ""),
            "title": raw_job.get("title", ""),
            "company": self.current_company.capitalize(),
            "country": country,
            "state": None,
            "city": location_str if location_str else None,
            "remote": raw_job.get("isRemote", False),
            "employment_type": raw_job.get("employmentType"),
            "salary_min": None, # Ashby often doesn't expose salary cleanly in the free JSON
            "salary_max": None,
            "currency": None,
            "job_url": raw_job.get("jobUrl", f"https://jobs.ashbyhq.com/{self.current_company}/{raw_job.get('id')}"),
            "apply_url": raw_job.get("applyUrl", f"https://jobs.ashbyhq.com/{self.current_company}/{raw_job.get('id')}?apply=true"),
            "description": clean_desc,
            "posted_date": raw_job.get("publishedAt", ""),
            "open_time": raw_job.get("openedAt"),
            "close_time": None,
            "source": self.source_name
        }
