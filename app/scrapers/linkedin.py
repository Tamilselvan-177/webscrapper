from typing import List, Dict, Any
from app.scrapers.base import BaseScraper
from app.models.filters import SearchFilters
from app.core.http_client import HTTPClient
from bs4 import BeautifulSoup
import httpx
import asyncio
import random
from fake_useragent import UserAgent

class LinkedInScraper(BaseScraper):
    def __init__(self):
        super().__init__()
        self.source_name = "LinkedIn"
        self.base_url = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings"
        # We need a dedicated httpx client for LinkedIn because it requires aggressive User-Agent rotation
        self.ua = UserAgent()

    async def _get_random_headers(self) -> dict:
        return {
            'User-Agent': self.ua.random,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
        }

    async def get_jobs(self, filters: SearchFilters, page: int = 1) -> List[Dict[str, Any]]:
        all_jobs = []
        limit_per_page = 25
        
        # In the context of LinkedIn, company acts as an additional keyword if provided
        search_terms = []
        if filters.keyword:
            search_terms.append(filters.keyword)
        if filters.company and filters.company.lower() != "linkedin":
            search_terms.append(filters.company)
            
        keyword_str = " ".join(search_terms) if search_terms else ""
        
        # Build location string
        location_parts = []
        if filters.city:
            location_parts.append(filters.city)
        if filters.country:
            location_parts.append(filters.country)
        location_str = ", ".join(location_parts) if location_parts else "Worldwide"
        
        # We will fetch up to 2 pages (50 jobs) max to avoid immediate IP ban on guest API
        max_pages = min(page, 2)
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            for current_page in range(max_pages):
                start_offset = current_page * limit_per_page
                
                params = {
                    "keywords": keyword_str,
                    "location": location_str,
                    "start": start_offset
                }
                
                headers = await self._get_random_headers()
                
                try:
                    response = await client.get(self.base_url, params=params, headers=headers)
                    if response.status_code == 429:
                        self.logger.warning("[LinkedIn] Rate limited! (429). Stopping fetch.")
                        break
                    
                    response.raise_for_status()
                    html_content = response.text
                    
                    if not html_content.strip():
                        break # End of results
                        
                    soup = BeautifulSoup(html_content, "html.parser")
                    job_cards = soup.find_all("li")
                    
                    if not job_cards:
                        break
                        
                    for card in job_cards:
                        try:
                            job_data = {}
                            
                            # ID and Job URL
                            link_elem = card.find("a", class_="base-card__full-link")
                            if not link_elem:
                                continue
                            
                            job_url = link_elem.get("href", "").split("?")[0]
                            job_data["job_url"] = job_url
                            
                            # ID is usually at the end of the URL: .../view/123456
                            job_id = job_url.split("-")[-1]
                            job_data["id"] = job_id
                            
                            # Title
                            title_elem = card.find("h3", class_="base-search-card__title")
                            job_data["title"] = title_elem.get_text(strip=True) if title_elem else ""
                            
                            # Company
                            company_elem = card.find("h4", class_="base-search-card__subtitle")
                            job_data["company"] = company_elem.get_text(strip=True) if company_elem else ""
                            
                            # Location
                            loc_elem = card.find("span", class_="job-search-card__location")
                            job_data["location_raw"] = loc_elem.get_text(strip=True) if loc_elem else ""
                            
                            # Date
                            date_elem = card.find("time", class_="job-search-card__listdate") or card.find("time", class_="job-search-card__listdate--new")
                            job_data["date"] = date_elem.get("datetime") if date_elem else ""
                            
                            all_jobs.append(job_data)
                            
                        except Exception as e:
                            self.logger.warning(f"[LinkedIn] Error parsing a job card: {e}")
                            continue
                            
                    # Polite sleep between pagination requests
                    if current_page < max_pages - 1:
                        await asyncio.sleep(random.uniform(2.0, 4.0))
                        
                except httpx.HTTPError as e:
                    self.logger.error(f"[LinkedIn] HTTP Error during fetch: {e}")
                    break
                    
        return all_jobs

    async def get_job_details(self, raw_job: Dict[str, Any]) -> Dict[str, Any]:
        # To avoid being banned immediately, we won't fetch individual job description pages
        # for every single result. The guest API is too fragile.
        # We will just pass the raw_job forward and rely on the summary data.
        return raw_job

    async def normalize(self, raw_job: Dict[str, Any]) -> Dict[str, Any]:
        
        # Attempt to parse location into city/country if possible
        loc_raw = raw_job.get("location_raw", "")
        city = loc_raw
        country = None
        if "," in loc_raw:
            parts = loc_raw.split(",")
            city = parts[0].strip()
            country = parts[-1].strip()

        return {
            "id": raw_job.get("id", ""),
            "title": raw_job.get("title", ""),
            "company": raw_job.get("company", ""),
            "country": country,
            "state": None,
            "city": city,
            "remote": "remote" in loc_raw.lower() or "remote" in raw_job.get("title", "").lower(),
            "employment_type": None,
            "salary_min": None,
            "salary_max": None,
            "currency": None,
            "job_url": raw_job.get("job_url", ""),
            "apply_url": raw_job.get("job_url", ""),
            "description": "Click the 'View Job' button to read the full description on LinkedIn.",
            "posted_date": raw_job.get("date", ""),
            "open_time": raw_job.get("date", ""),
            "close_time": None,
            "source": self.source_name
        }
