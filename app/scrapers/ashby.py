import asyncio
import logging
import httpx
from typing import List, Dict, Any
from app.scrapers.base import BaseScraper
from app.models.filters import SearchFilters
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

class AshbyScraper(BaseScraper):
    """
    Ashby HQ Scraper querying public job board APIs.
    Supports individual company querying or parallel querying of a top tech startup pool.
    """
    DEFAULT_COMPANIES = [
        "openai", "ramp", "notion", "cohere", 
        "zapier", "linear", "ashby"
    ]

    def __init__(self):
        super().__init__()
        self.source_name = "Ashby"
        self.base_url = "https://api.ashbyhq.com/posting-api/job-board"
        self.current_company = "ashby"

    async def _fetch_company_jobs(self, company: str, filters: SearchFilters) -> List[Dict[str, Any]]:
        url = f"{self.base_url}/{company}"
        try:
            async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
                response = await client.get(url, headers={"Accept": "application/json"})
                if response.status_code != 200:
                    return []
                data = response.json()
                raw_jobs = data.get("jobs", [])
                
                valid_jobs = []
                for job in raw_jobs:
                    if not isinstance(job, dict):
                        continue
                    if filters.keyword:
                        kw = filters.keyword.lower()
                        title = job.get("title", "").lower()
                        desc = job.get("descriptionHtml", "").lower()
                        tech_syns = ["develop", "engineer", "software", "dev", "program", "cod", "backend", "frontend", "fullstack", "data", "cloud", "tech", "ai", "ml"]
                        is_tech = any(t in kw for t in tech_syns)
                        has_tech_title = any(t in title or t in desc for t in tech_syns)
                        if not (any(w in title or w in desc for w in kw.split()) or (is_tech and has_tech_title)):
                            continue
                    job["_company"] = company
                    valid_jobs.append(job)
                return valid_jobs[:20]  # Cap per company
        except Exception as e:
            logger.debug(f"[Ashby] Error fetching jobs for '{company}': {e}")
            return []

    async def get_jobs(self, filters: SearchFilters, page: int = 1) -> List[Dict[str, Any]]:
        company = (filters.company or "").strip().lower()
        if company and company != "ashby":
            self.current_company = company 
            return await self._fetch_company_jobs(company, filters)
        
        # Query default company pool in parallel
        logger.info(f"[Ashby] Querying default pool for: {filters.keyword}")
        tasks = [self._fetch_company_jobs(c, filters) for c in self.DEFAULT_COMPANIES]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        combined = []
        for res in results:
            if isinstance(res, list):
                combined.extend(res)
        return combined[:40]

    async def get_job_details(self, raw_job: Dict[str, Any]) -> Dict[str, Any]:
        # Ashby's posting-api endpoint already returns full descriptionHtml and descriptionPlain
        return raw_job

    async def normalize(self, raw_job: Dict[str, Any]) -> Dict[str, Any]:
        company_name = raw_job.get("_company", self.current_company)
        location = raw_job.get("location", "")
        if isinstance(location, dict):
            location_str = location.get("address", {}).get("addressLocality", "")
            country = location.get("address", {}).get("addressCountry", "")
        else:
            location_str = str(location)
            country = None
            
        desc_html = raw_job.get("descriptionHtml", "")
        if desc_html:
            soup = BeautifulSoup(desc_html, "html.parser")
            for script in soup(["script", "style"]):
                script.decompose()
            clean_desc = soup.get_text(separator="\n", strip=True)
        else:
            clean_desc = raw_job.get("descriptionPlain", "")

        return {
            "id": str(raw_job.get("id", "")),
            "title": raw_job.get("title", ""),
            "company": company_name.capitalize(),
            "country": country,
            "state": None,
            "city": location_str if location_str else None,
            "remote": raw_job.get("isRemote", False),
            "employment_type": raw_job.get("employmentType"),
            "salary_min": None,
            "salary_max": None,
            "currency": None,
            "job_url": raw_job.get("jobUrl", f"https://jobs.ashbyhq.com/{company_name}/{raw_job.get('id')}"),
            "apply_url": raw_job.get("applyUrl", f"https://jobs.ashbyhq.com/{company_name}/{raw_job.get('id')}?apply=true"),
            "description": clean_desc,
            "posted_date": raw_job.get("publishedAt", ""),
            "open_time": raw_job.get("openedAt"),
            "close_time": None,
            "source": self.source_name,
            "company_logo": None,
            "applicants": None,
        }
