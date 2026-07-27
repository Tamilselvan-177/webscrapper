import asyncio
import httpx
import logging
from typing import List, Dict, Any
from bs4 import BeautifulSoup
from app.scrapers.base import BaseScraper
from app.models.filters import SearchFilters

logger = logging.getLogger(__name__)

class SmartRecruitersScraper(BaseScraper):
    """
    SmartRecruiters ATS Scraper using httpx.
    Queries a pool of known companies when no company slug is given.
    """
    BASE = "https://api.smartrecruiters.com/v1/companies"
    DEFAULT_COMPANIES = [
        "smartrecruiters", "visa", "equinox", "fresenius", "colliers",
        "ubisoft", "square", "biogen", "skechers"
    ]

    def __init__(self):
        super().__init__()
        self.source_name = "SmartRecruiters"
        self.current_company = "Zalando"

    async def _fetch_company_jobs(self, company: str, filters: SearchFilters) -> List[Dict[str, Any]]:
        url = f"{self.BASE}/{company}/postings"
        params: dict = {"limit": 50}
        if filters.keyword:
            params["q"] = filters.keyword
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.get(url, params=params, headers={"Accept": "application/json"})
                if resp.status_code != 200:
                    logger.debug(f"[SmartRecruiters] {company} returned {resp.status_code}")
                    return []
                data = resp.json()
                jobs = data.get("content", [])
                for j in jobs:
                    j["_company"] = company
                return jobs[:15]
        except Exception as e:
            logger.debug(f"[SmartRecruiters] Error fetching {company}: {e}")
            return []

    async def get_jobs(self, filters: SearchFilters, page: int = 1) -> List[Dict[str, Any]]:
        company = (filters.company or "").strip()
        if company and company.lower() not in ("smartrecruiters", ""):
            self.current_company = company
            return await self._fetch_company_jobs(company, filters)

        # Query default pool in parallel
        logger.info(f"[SmartRecruiters] Querying default pool for: {filters.keyword}")
        tasks = [self._fetch_company_jobs(c, filters) for c in self.DEFAULT_COMPANIES]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        combined = []
        for res in results:
            if isinstance(res, list):
                combined.extend(res)
        return combined[:40]

    async def get_job_details(self, raw_job: Dict[str, Any]) -> Dict[str, Any]:
        company = raw_job.get("_company", self.current_company)
        job_id = raw_job.get("id")
        if not job_id:
            return raw_job
        try:
            url = f"{self.BASE}/{company}/postings/{job_id}"
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.get(url, headers={"Accept": "application/json"})
                if resp.status_code == 200:
                    raw_job.update(resp.json())
        except Exception as e:
            logger.debug(f"[SmartRecruiters] Detail fetch failed: {e}")
        return raw_job

    async def normalize(self, raw_job: Dict[str, Any]) -> Dict[str, Any]:
        location = raw_job.get("location") or {}
        company_name = raw_job.get("_company", self.current_company)

        job_ad = raw_job.get("jobAd") or {}
        sections = job_ad.get("sections") or {}
        desc_parts = []
        for section_name in ["companyDescription", "jobDescription", "qualifications", "additionalInformation"]:
            section = sections.get(section_name) or {}
            title = section.get("title", "")
            text = section.get("text", "")
            if text:
                if title:
                    desc_parts.append(f"## {title}")
                desc_parts.append(text)
        full_html = "\n".join(desc_parts)
        soup = BeautifulSoup(full_html, "html.parser")
        description = soup.get_text(separator="\n", strip=True)

        return {
            "id": str(raw_job.get("id", "")),
            "title": raw_job.get("name", ""),
            "company": company_name.capitalize(),
            "country": location.get("country", ""),
            "state": location.get("region", ""),
            "city": location.get("city", ""),
            "remote": location.get("remote", False),
            "employment_type": (raw_job.get("typeOfEmployment") or {}).get("label"),
            "salary_min": None,
            "salary_max": None,
            "currency": None,
            "job_url": f"https://jobs.smartrecruiters.com/{company_name}/{raw_job.get('id')}",
            "apply_url": f"https://jobs.smartrecruiters.com/{company_name}/{raw_job.get('id')}?apply=true",
            "description": description,
            "posted_date": raw_job.get("releasedDate", ""),
            "open_time": raw_job.get("releasedDate", ""),
            "close_time": raw_job.get("expirationDate"),
            "source": self.source_name,
            "company_logo": None,
            "applicants": None,
        }
