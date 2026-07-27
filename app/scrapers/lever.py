from typing import List, Dict, Any
from app.scrapers.base import BaseScraper
from app.models.filters import SearchFilters
from app.core.http_client import HTTPClient
import asyncio
import logging

logger = logging.getLogger(__name__)

class LeverScraper(BaseScraper):
    def __init__(self):
        super().__init__()
        self.source_name = "Lever"
        self.base_url = "https://api.lever.co/v0/postings"
        self.client = HTTPClient(base_url=self.base_url)
        self.default_companies = [
            "palantir", "sentry", "auth0", "kpmg", "retina", "plaid",
            "netflix", "spotify", "stripe", "airbnb", "vercel", "linear"
        ]

    async def _fetch_company_jobs(self, comp: str, filters: SearchFilters) -> List[Dict[str, Any]]:
        params = {"mode": "json"}
        if filters.city:
            params["location"] = filters.city
        try:
            response = await self.client.get(f"/{comp}", params=params)
            raw_jobs = response.json()
            if isinstance(raw_jobs, list):
                valid_jobs = []
                for job in raw_jobs:
                    if not isinstance(job, dict):
                        continue
                    if filters.keyword:
                        kw = filters.keyword.lower()
                        title = job.get("text", "").lower()
                        desc = job.get("descriptionPlain", "").lower()
                        tech_syns = ["develop", "engineer", "software", "dev", "program", "cod", "backend", "frontend", "fullstack", "data", "cloud", "tech"]
                        is_tech_search = any(t in kw for t in tech_syns)
                        has_tech_title = any(t in title or t in desc for t in tech_syns)
                        if not (any(w in title or w in desc for w in kw.split()) or (is_tech_search and has_tech_title)):
                            continue
                    valid_jobs.append(job)
                return valid_jobs[:20]  # Cap per company
        except Exception as e:
            logger.debug(f"[Lever] Could not fetch for {comp}: {e}")
        return []

    async def get_jobs(self, filters: SearchFilters, page: int = 1) -> List[Dict[str, Any]]:
        company = filters.company.lower() if filters.company else "lever"
        self.current_company = company 
        
        # If specific valid company requested, query it
        if company and company != "lever":
            return await self._fetch_company_jobs(company, filters)
        
        # If no specific company or default 'lever', query top active tech companies in parallel
        logger.info(f"[Lever] Querying default active companies for keyword: {filters.keyword}")
        tasks = [self._fetch_company_jobs(comp, filters) for comp in self.default_companies]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        combined_jobs = []
        for res in results:
            if isinstance(res, list):
                combined_jobs.extend(res)
                
        # If still no results, fetch all from palantir as guaranteed sample pool
        if not combined_jobs:
            combined_jobs = await self._fetch_company_jobs("palantir", SearchFilters(source="lever"))
            
        return combined_jobs[:40]

    async def get_job_details(self, raw_job: Dict[str, Any]) -> Dict[str, Any]:
        return raw_job

    async def normalize(self, raw_job: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(raw_job, dict):
            return {}
            
        categories = raw_job.get("categories", {})
        location_str = categories.get("location", "") if isinstance(categories, dict) else ""
        
        parts = [p.strip() for p in location_str.split(",")]
        city = parts[0] if len(parts) > 0 else "Remote / Office"
        country = parts[-1] if len(parts) > 1 else "United States"
        state = parts[1] if len(parts) > 2 else None
        
        workplace_type = raw_job.get("workplaceType", "").lower()
        remote = workplace_type == "remote" or "remote" in location_str.lower()
        
        desc_plain = raw_job.get("descriptionPlain", "")
        lists_content = ""
        for lst in raw_job.get("lists", []):
            if isinstance(lst, dict):
                text = lst.get("text", "")
                content = lst.get("content", "")
                lists_content += f"\n\n{text}\n{content}"
            
        full_desc = f"{desc_plain}{lists_content}".strip()
        if not full_desc:
            full_desc = raw_job.get("description", "")

        team = categories.get("team", "Engineering") if isinstance(categories, dict) else "Engineering"
        company_name = categories.get("department", "Tech Employer") if isinstance(categories, dict) and categories.get("department") else team

        return {
            "id": str(raw_job.get("id", "")),
            "title": raw_job.get("text", "Software Engineer"),
            "company": f"Lever Tech ({company_name})",
            "country": country,
            "state": state,
            "city": city,
            "remote": remote,
            "employment_type": categories.get("commitment", "Full-time") if isinstance(categories, dict) else "Full-time",
            "salary_min": None,
            "salary_max": None,
            "currency": "USD",
            "job_url": raw_job.get("hostedUrl", ""),
            "apply_url": raw_job.get("applyUrl", "") or raw_job.get("hostedUrl", ""),
            "description": full_desc,
            "posted_date": "",
            "open_time": "",
            "close_time": None,
            "source": self.source_name,
            "company_logo": None,
            "applicants": None
        }
