from typing import List, Dict, Any
from app.scrapers.base import BaseScraper
from app.models.filters import SearchFilters
from app.core.http_client import HTTPClient
import xml.etree.ElementTree as ET

class PersonioScraper(BaseScraper):
    def __init__(self):
        super().__init__()
        self.source_name = "Personio"
        self.base_url = "https://{company}.jobs.personio.de"
        self.client = HTTPClient() # Base URL is dynamic for Personio

    async def get_jobs(self, filters: SearchFilters, page: int = 1) -> List[Dict[str, Any]]:
        company = filters.company.lower() if filters.company else "personio"
        self.current_company = company 
        
        url = f"https://{company}.jobs.personio.de/xml"
        
        response = await self.client.get(url)
        xml_content = response.text
        
        try:
            root = ET.fromstring(xml_content)
        except ET.ParseError:
            return []
            
        all_jobs = []
        for position in root.findall("position"):
            # Convert XML element to a dictionary for easier handling
            job_dict = {}
            for child in position:
                if child.tag == "jobDescriptions":
                    job_dict[child.tag] = [{"name": jd.find("name").text if jd.find("name") is not None else "", 
                                            "value": jd.find("value").text if jd.find("value") is not None else ""} 
                                           for jd in child.findall("jobDescription")]
                else:
                    job_dict[child.tag] = child.text
            all_jobs.append(job_dict)
            
        # Local filtering
        filtered_jobs = []
        for job in all_jobs:
            if filters.keyword:
                kw = filters.keyword.lower()
                title = (job.get("name") or "").lower()
                if kw not in title:
                    continue
            if filters.country:
                country = filters.country.lower()
                # Personio typically stores location in "office" or separate tags depending on config
                job_office = (job.get("office") or "").lower()
                if country not in job_office:
                    continue
                    
            filtered_jobs.append(job)
            
        return filtered_jobs

    async def get_job_details(self, raw_job: Dict[str, Any]) -> Dict[str, Any]:
        # XML feed contains all details
        return raw_job

    async def normalize(self, raw_job: Dict[str, Any]) -> Dict[str, Any]:
        # Build description
        desc_parts = []
        for jd in raw_job.get("jobDescriptions", []):
            if jd["name"]:
                desc_parts.append(f"<h2>{jd['name']}</h2>")
            if jd["value"]:
                desc_parts.append(jd["value"])
                
        full_description = "\n".join(desc_parts).strip()
        
        # Personio sometimes includes a department and office
        department = raw_job.get("department")
        office = raw_job.get("office", "")
        
        # Remote usually specified in office or title
        remote = "remote" in office.lower() or "remote" in (raw_job.get("name") or "").lower()
        
        return {
            "id": raw_job.get("id", ""),
            "title": raw_job.get("name", ""),
            "company": self.current_company.capitalize(),
            "country": None,
            "state": None,
            "city": office, # Often just the city name
            "remote": remote,
            "employment_type": raw_job.get("employmentType"),
            "salary_min": None,
            "salary_max": None,
            "currency": None,
            "job_url": f"https://{self.current_company}.jobs.personio.de/job/{raw_job.get('id')}",
            "apply_url": f"https://{self.current_company}.jobs.personio.de/job/{raw_job.get('id')}#apply",
            "description": full_description,
            "posted_date": raw_job.get("createdAt", ""), 
            "open_time": raw_job.get("createdAt", ""),
            "close_time": None,
            "source": self.source_name
        }
