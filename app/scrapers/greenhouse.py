import re
import httpx
import asyncio
import logging
from typing import List, Dict, Any
from bs4 import BeautifulSoup
from app.scrapers.base import BaseScraper
from app.models.filters import SearchFilters

logger = logging.getLogger(__name__)

class GreenhouseScraper(BaseScraper):
    """
    Greenhouse ATS Scraper using direct httpx calls (no deprecated HTTPClient).
    Searches across a pool of known tech companies when no company slug is provided.
    """
    BASE = "https://boards-api.greenhouse.io/v1/boards"
    DEFAULT_COMPANIES = [
        "contentful", "stripe", "notion", "figma", "databricks",
        "squarespace", "hubspot", "zapier", "intercom", "datadog"
    ]

    def __init__(self):
        super().__init__()
        self.source_name = "Greenhouse"
        self.current_company = "contentful"

    async def _fetch_company_jobs(self, company: str, filters: SearchFilters) -> List[Dict[str, Any]]:
        url = f"{self.BASE}/{company}/jobs"
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.get(url, headers={"Accept": "application/json"})
                if resp.status_code != 200:
                    logger.debug(f"[Greenhouse] {company} returned {resp.status_code}")
                    return []
                data = resp.json()
                jobs = data.get("jobs", [])
                # Keyword filter
                if filters.keyword:
                    kw_words = filters.keyword.lower().split()
                    jobs = [
                        j for j in jobs
                        if any(w in j.get("title", "").lower() for w in kw_words)
                    ]
                # Tag each job with the company
                for j in jobs:
                    j["_company"] = company
                return jobs[:15]
        except Exception as e:
            logger.debug(f"[Greenhouse] Error fetching {company}: {e}")
            return []

    async def get_jobs(self, filters: SearchFilters, page: int = 1) -> List[Dict[str, Any]]:
        company = (filters.company or "").strip().lower()
        if company and company not in ("greenhouse", ""):
            self.current_company = company
            return await self._fetch_company_jobs(company, filters)

        # No company specified — query the default pool in parallel
        logger.info(f"[Greenhouse] Querying default pool for keyword: {filters.keyword}")
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
            url = f"{self.BASE}/{company}/jobs/{job_id}"
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.get(url, headers={"Accept": "application/json"})
                if resp.status_code == 200:
                    detail = resp.json()
                    raw_job.update(detail)
        except Exception as e:
            logger.debug(f"[Greenhouse] Detail fetch failed for {job_id}: {e}")
        return raw_job

    async def normalize(self, raw_job: Dict[str, Any]) -> Dict[str, Any]:
        location_str = raw_job.get("location", {}).get("name", "") if isinstance(raw_job.get("location"), dict) else ""
        parts = [p.strip() for p in location_str.split(",")]
        city = parts[0] if parts else None
        country = parts[-1] if len(parts) > 1 else None
        state = parts[1] if len(parts) > 2 else None

        raw_html = raw_job.get("content", "")
        description = None
        salary_min = None
        salary_max = None
        currency = None

        if raw_html:
            soup = BeautifulSoup(raw_html, "html.parser")
            description = soup.get_text(separator="\n", strip=True)
            salary_match = re.search(
                r'([$£€])\s*([\d,]+(?:k)?)\s*[-–to]+\s*(?:[$£€])?\s*([\d,]+(?:k)?)',
                description, re.IGNORECASE
            )
            if salary_match:
                sym = salary_match.group(1)
                try:
                    salary_min = float(salary_match.group(2).replace(",", "").replace("k", "000"))
                    salary_max = float(salary_match.group(3).replace(",", "").replace("k", "000"))
                    currency = {"$": "USD", "£": "GBP", "€": "EUR"}.get(sym, "USD")
                except ValueError:
                    pass

        company_name = raw_job.get("_company", self.current_company)

        return {
            "id": str(raw_job.get("internal_job_id") or raw_job.get("id", "")),
            "title": raw_job.get("title", ""),
            "company": company_name.capitalize(),
            "country": country,
            "state": state,
            "city": city,
            "remote": "remote" in location_str.lower() or "remote" in raw_job.get("title", "").lower(),
            "employment_type": None,
            "salary_min": salary_min,
            "salary_max": salary_max,
            "currency": currency,
            "job_url": raw_job.get("absolute_url", ""),
            "apply_url": (raw_job.get("absolute_url", "") or "") + "#app",
            "description": description or "",
            "posted_date": raw_job.get("updated_at", ""),
            "open_time": raw_job.get("opened_at", ""),
            "close_time": raw_job.get("closed_at"),
            "source": self.source_name,
            "company_logo": None,
            "applicants": None,
        }
