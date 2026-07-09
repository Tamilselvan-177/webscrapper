import re
from typing import List, Dict, Any
from bs4 import BeautifulSoup
from app.scrapers.base import BaseScraper
from app.models.filters import SearchFilters
from app.core.http_client import HTTPClient

class GreenhouseScraper(BaseScraper):
    def __init__(self):
        super().__init__()
        self.source_name = "Greenhouse"
        self.base_url = "https://boards-api.greenhouse.io/v1/boards"
        self.client = HTTPClient(base_url=self.base_url)

    async def get_jobs(self, filters: SearchFilters, page: int = 1) -> List[Dict[str, Any]]:
        company = filters.company.lower() if filters.company else "contentful"
        # Store company on self so we can use it in normalize
        self.current_company = company 
        
        url = f"/{company}/jobs"
        response = await self.client.get(url)
        data = response.json()
        raw_jobs = data.get("jobs", [])
        
        # Local filtering since Greenhouse returns everything
        filtered_jobs = []
        for job in raw_jobs:
            if filters.country and filters.country.lower() not in job.get("location", {}).get("name", "").lower():
                continue
            if filters.keyword:
                kw = filters.keyword.lower()
                title = job.get("title", "").lower()
                # strict vs fuzzy keyword logic can go here. We'll do partial match for now.
                if kw not in title:
                    continue
            filtered_jobs.append(job)
            
        return filtered_jobs

    async def get_job_details(self, raw_job: Dict[str, Any]) -> Dict[str, Any]:
        job_id = raw_job.get("id")
        url = f"/{self.current_company}/jobs/{job_id}"
        response = await self.client.get(url)
        return response.json()

    async def normalize(self, raw_job: Dict[str, Any]) -> Dict[str, Any]:
        location_str = raw_job.get("location", {}).get("name", "")
        parts = [p.strip() for p in location_str.split(",")]
        city = parts[0] if len(parts) > 0 else None
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
            
            # Simple Regex to catch things like $100,000 - $150,000 or 50k - 70k
            salary_match = re.search(r'([$])\s*([\d,]+(?:k)?)\s*[-to]+\s*(?:[$])?\s*([\d,]+(?:k)?)', description, re.IGNORECASE)
            if salary_match:
                currency_symbol = salary_match.group(1)
                min_s = salary_match.group(2).lower().replace(',', '').replace('k', '000')
                max_s = salary_match.group(3).lower().replace(',', '').replace('k', '000')
                
                try:
                    salary_min = float(min_s)
                    salary_max = float(max_s)
                    curr_map = {'$': 'USD', '': 'EUR', '': 'GBP'}
                    currency = curr_map.get(currency_symbol, "USD")
                except ValueError:
                    pass

        return {
            "id": str(raw_job.get("internal_job_id", raw_job.get("id"))),
            "title": raw_job.get("title", ""),
            "company": self.current_company.capitalize(),
            "country": country,
            "state": state,
            "city": city,
            "remote": "remote" in location_str.lower() or "remote" in raw_job.get("title", "").lower(),
            "employment_type": None,
            "salary_min": salary_min,
            "salary_max": salary_max,
            "currency": currency,
            "job_url": raw_job.get("absolute_url", ""),
            "apply_url": raw_job.get("absolute_url", "") + "#app",
            "description": description,
            "posted_date": raw_job.get("updated_at", ""),
            "open_time": raw_job.get("opened_at"),
            "close_time": raw_job.get("closed_at"),
            "source": self.source_name
        }
