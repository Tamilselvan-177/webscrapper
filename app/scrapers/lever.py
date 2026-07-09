from typing import List, Dict, Any
from app.scrapers.base import BaseScraper
from app.models.filters import SearchFilters
from app.core.http_client import HTTPClient
import re

class LeverScraper(BaseScraper):
    def __init__(self):
        super().__init__()
        self.source_name = "Lever"
        self.base_url = "https://api.lever.co/v0/postings"
        self.client = HTTPClient(base_url=self.base_url)

    async def get_jobs(self, filters: SearchFilters, page: int = 1) -> List[Dict[str, Any]]:
        company = filters.company.lower() if filters.company else "lever"
        self.current_company = company 
        
        url = f"/{company}"
        # Leverage parameters if possible, but Lever's v0 API is mostly fetch-all
        params = {"mode": "json"}
        if filters.city:
            params["location"] = filters.city
        if filters.keyword:
            params["department"] = filters.keyword # Lever maps some keywords to department
            
        response = await self.client.get(url, params=params)
        raw_jobs = response.json()
        
        # Local filtering for exact matches that the API might ignore
        filtered_jobs = []
        for job in raw_jobs:
            # Check keyword in title if provided
            if filters.keyword:
                kw = filters.keyword.lower()
                title = job.get("text", "").lower()
                if kw not in title:
                    continue
            filtered_jobs.append(job)
            
        return filtered_jobs

    async def get_job_details(self, raw_job: Dict[str, Any]) -> Dict[str, Any]:
        # Lever returns full details in the initial list payload, no need to fetch again.
        return raw_job

    async def normalize(self, raw_job: Dict[str, Any]) -> Dict[str, Any]:
        categories = raw_job.get("categories", {})
        location_str = categories.get("location", "")
        
        # Parse Lever location format (e.g. "San Francisco, CA" or "London, UK")
        parts = [p.strip() for p in location_str.split(",")]
        city = parts[0] if len(parts) > 0 else None
        country = parts[-1] if len(parts) > 1 else None
        state = parts[1] if len(parts) > 2 else None
        
        # Determine remote status
        workplace_type = raw_job.get("workplaceType", "").lower()
        remote = workplace_type == "remote" or categories.get("location", "").lower() == "remote"
        
        # Build unified description
        desc_plain = raw_job.get("descriptionPlain", "")
        desc_lists = ""
        for lst in raw_job.get("lists", []):
            desc_lists += f"\n\n{lst.get('text', '')}\n"
            desc_lists += "\n".join([f"- {item.get('text', '')}" for item in lst.get('content', [])])
        
        full_description = desc_plain + desc_lists
        
        # Try to extract salary
        salary_min = None
        salary_max = None
        currency = None
        salary_match = re.search(r'([$])\s*([\d,]+(?:k)?)\s*[-to]+\s*(?:[$])?\s*([\d,]+(?:k)?)', full_description, re.IGNORECASE)
        if salary_match:
            currency_symbol = salary_match.group(1)
            min_s = salary_match.group(2).lower().replace(',', '').replace('k', '000')
            max_s = salary_match.group(3).lower().replace(',', '').replace('k', '000')
            try:
                salary_min = float(min_s)
                salary_max = float(max_s)
                curr_map = {'$': 'USD'}
                currency = curr_map.get(currency_symbol, "USD")
            except ValueError:
                pass

        return {
            "id": raw_job.get("id", ""),
            "title": raw_job.get("text", ""),
            "company": self.current_company.capitalize(),
            "country": country,
            "state": state,
            "city": city,
            "remote": remote,
            "employment_type": categories.get("commitment"),
            "salary_min": salary_min,
            "salary_max": salary_max,
            "currency": currency,
            "job_url": raw_job.get("hostedUrl", ""),
            "apply_url": raw_job.get("applyUrl", ""),
            "description": full_description.strip(),
            "posted_date": str(raw_job.get("createdAt", "")),
            "open_time": None,
            "close_time": None,
            "source": self.source_name
        }
