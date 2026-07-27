import asyncio
import httpx
import logging
import xml.etree.ElementTree as ET
from typing import List, Dict, Any
from app.scrapers.base import BaseScraper
from app.models.filters import SearchFilters

logger = logging.getLogger(__name__)

class PersonioScraper(BaseScraper):
    """
    Personio ATS Scraper using httpx + company pool.
    Each company has its own Personio subdomain: {company}.jobs.personio.de
    """
    DEFAULT_COMPANIES = [
        "personio", "sumup", "n26", "flixbus", "kfzteile24",
        "idealo", "aboutyou", "commercetools", "raisin", "adjust"
    ]

    def __init__(self):
        super().__init__()
        self.source_name = "Personio"
        self.current_company = "personio"

    async def _fetch_company_jobs(self, company: str, filters: SearchFilters) -> List[Dict[str, Any]]:
        url = f"https://{company}.jobs.personio.de/xml"
        try:
            async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
                resp = await client.get(url)
                if resp.status_code != 200:
                    return []
                root = ET.fromstring(resp.text)
                all_jobs = []
                for position in root.findall("position"):
                    job_dict: Dict[str, Any] = {"_company": company}
                    for child in position:
                        if child.tag == "jobDescriptions":
                            job_dict[child.tag] = [
                                {
                                    "name": (jd.find("name").text or "") if jd.find("name") is not None else "",
                                    "value": (jd.find("value").text or "") if jd.find("value") is not None else "",
                                }
                                for jd in child.findall("jobDescription")
                            ]
                        else:
                            job_dict[child.tag] = child.text
                    if filters.keyword:
                        kw_words = filters.keyword.lower().split()
                        title = (job_dict.get("name") or "").lower()
                        if not any(w in title for w in kw_words):
                            continue
                    all_jobs.append(job_dict)
                return all_jobs[:15]
        except Exception as e:
            logger.debug(f"[Personio] Error fetching {company}: {e}")
            return []

    async def get_jobs(self, filters: SearchFilters, page: int = 1) -> List[Dict[str, Any]]:
        company = (filters.company or "").strip().lower()
        if company and company not in ("personio", ""):
            self.current_company = company
            return await self._fetch_company_jobs(company, filters)

        # Query default pool in parallel
        logger.info(f"[Personio] Querying default pool for: {filters.keyword}")
        tasks = [self._fetch_company_jobs(c, filters) for c in self.DEFAULT_COMPANIES]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        combined = []
        for res in results:
            if isinstance(res, list):
                combined.extend(res)
        return combined[:40]

    async def get_job_details(self, raw_job: Dict[str, Any]) -> Dict[str, Any]:
        return raw_job

    async def normalize(self, raw_job: Dict[str, Any]) -> Dict[str, Any]:
        desc_parts = []
        for jd in raw_job.get("jobDescriptions", []):
            if jd.get("name"):
                desc_parts.append(f"## {jd['name']}")
            if jd.get("value"):
                desc_parts.append(jd["value"])
        full_description = "\n".join(desc_parts).strip()

        company_name = raw_job.get("_company", self.current_company)
        office = raw_job.get("office", "")
        remote = "remote" in office.lower() or "remote" in (raw_job.get("name") or "").lower()

        return {
            "id": str(raw_job.get("id", "")),
            "title": raw_job.get("name", ""),
            "company": company_name.capitalize(),
            "country": None,
            "state": None,
            "city": office,
            "remote": remote,
            "employment_type": raw_job.get("employmentType"),
            "salary_min": None,
            "salary_max": None,
            "currency": None,
            "job_url": f"https://{company_name}.jobs.personio.de/job/{raw_job.get('id')}",
            "apply_url": f"https://{company_name}.jobs.personio.de/job/{raw_job.get('id')}#apply",
            "description": full_description,
            "posted_date": raw_job.get("createdAt", ""),
            "open_time": raw_job.get("createdAt", ""),
            "close_time": None,
            "source": self.source_name,
            "company_logo": None,
            "applicants": None,
        }
