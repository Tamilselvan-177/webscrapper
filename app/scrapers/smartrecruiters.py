from typing import List, Dict, Any
from app.scrapers.base import BaseScraper
from app.models.filters import SearchFilters
from app.core.http_client import HTTPClient
from bs4 import BeautifulSoup

class SmartRecruitersScraper(BaseScraper):
    def __init__(self):
        super().__init__()
        self.source_name = "SmartRecruiters"
        self.base_url = "https://api.smartrecruiters.com/v1/companies"
        self.client = HTTPClient(base_url=self.base_url)

    async def get_jobs(self, filters: SearchFilters, page: int = 1) -> List[Dict[str, Any]]:
        company = filters.company.lower() if filters.company else "smartrecruiters"
        self.current_company = company 
        
        all_jobs = []
        offset = 0
        limit = 100
        
        while True:
            url = f"/{company}/postings"
            params = {"offset": offset, "limit": limit}
            if filters.keyword:
                params["q"] = filters.keyword
            # SmartRecruiters API doesn't filter perfectly by location or department without specific IDs in some versions,
            # so we fetch and filter locally if it's complex.
            
            response = await self.client.get(url, params=params)
            data = response.json()
            content = data.get("content", [])
            
            if not content:
                break
                
            all_jobs.extend(content)
            
            total_found = data.get("totalFound", 0)
            offset += limit
            if offset >= total_found:
                break
                
        # Local Filtering for robustness
        filtered_jobs = []
        for job in all_jobs:
            if filters.country:
                job_country = job.get("location", {}).get("country", "").lower()
                if filters.country.lower() not in job_country:
                    continue
            if filters.city:
                job_city = job.get("location", {}).get("city", "").lower()
                if filters.city.lower() not in job_city:
                    continue
            filtered_jobs.append(job)
            
        return filtered_jobs

    async def get_job_details(self, raw_job: Dict[str, Any]) -> Dict[str, Any]:
        job_id = raw_job.get("id")
        url = f"/{self.current_company}/postings/{job_id}"
        response = await self.client.get(url)
        return response.json()

    async def normalize(self, raw_job: Dict[str, Any]) -> Dict[str, Any]:
        location = raw_job.get("location", {})
        
        # Build unified description from sections
        job_ad = raw_job.get("jobAd", {})
        sections = job_ad.get("sections", {})
        
        desc_parts = []
        for section_name in ["companyDescription", "jobDescription", "qualifications", "additionalInformation"]:
            section = sections.get(section_name, {})
            title = section.get("title", "")
            text = section.get("text", "")
            if text:
                if title:
                    desc_parts.append(f"<h2>{title}</h2>")
                desc_parts.append(text)
                
        full_html = "\n".join(desc_parts)
        
        soup = BeautifulSoup(full_html, "html.parser")
        clean_description = soup.get_text(separator="\n", strip=True)
        
        remote = raw_job.get("location", {}).get("remote", False)

        return {
            "id": raw_job.get("id", ""),
            "title": raw_job.get("name", ""),
            "company": self.current_company.capitalize(),
            "country": location.get("country", ""),
            "state": location.get("region", ""),
            "city": location.get("city", ""),
            "remote": remote,
            "employment_type": raw_job.get("typeOfEmployment", {}).get("label"),
            "salary_min": None,
            "salary_max": None,
            "currency": None,
            "job_url": f"https://jobs.smartrecruiters.com/{self.current_company}/{raw_job.get('id')}",
            "apply_url": f"https://jobs.smartrecruiters.com/{self.current_company}/{raw_job.get('id')}?apply=true",
            "description": clean_description,
            "posted_date": raw_job.get("releasedDate", ""),
            "open_time": raw_job.get("releasedDate", ""),
            "close_time": raw_job.get("expirationDate"),
            "source": self.source_name
        }
