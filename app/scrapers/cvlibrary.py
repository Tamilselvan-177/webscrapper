from typing import List, Dict, Any
from app.scrapers.base import BaseScraper
from app.models.filters import SearchFilters
from bs4 import BeautifulSoup
import httpx
import logging
from fake_useragent import UserAgent

logger = logging.getLogger(__name__)

class CvLibraryScraper(BaseScraper):
    def __init__(self):
        super().__init__()
        self.source_name = "CV-Library"
        self.base_url = "https://www.cv-library.co.uk/search-jobs"
        self.ua = UserAgent()

    async def _get_headers(self) -> dict:
        return {
            'User-Agent': self.ua.random,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-GB,en;q=0.5',
        }

    async def get_jobs(self, filters: SearchFilters, page: int = 1) -> List[Dict[str, Any]]:
        all_jobs = []
        keyword = " ".join(filter(None, [filters.keyword, filters.company]))
        location = filters.city or ""

        params = {
            "q": keyword,
            "geo": location,
            "p": page,
        }

        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            try:
                response = await client.get(self.base_url, params=params, headers=await self._get_headers())
                response.raise_for_status()
                soup = BeautifulSoup(response.text, "html.parser")

                job_cards = soup.find_all("li", class_="job")
                if not job_cards:
                    job_cards = soup.find_all("article")

                for card in job_cards:
                    try:
                        job_data = {}
                        link = card.find("a", class_="job-title") or card.find("h2", class_="title")
                        if not link:
                            link = card.find("a", href=True)
                        if not link:
                            continue

                        href = link.get("href", "")
                        job_data["job_url"] = href if href.startswith("http") else f"https://www.cv-library.co.uk{href}"
                        job_data["id"] = href.split("/")[-1].split("?")[0] if href else ""
                        job_data["title"] = link.get_text(strip=True)

                        company_elem = card.find(class_="company") or card.find(class_="employer")
                        job_data["company"] = company_elem.get_text(strip=True) if company_elem else ""

                        loc_elem = card.find(class_="location") or card.find(class_="job-location")
                        job_data["location_raw"] = loc_elem.get_text(strip=True) if loc_elem else ""

                        date_elem = card.find("time") or card.find(class_="date-posted")
                        job_data["date"] = date_elem.get_text(strip=True) if date_elem else ""

                        if job_data.get("title"):
                            all_jobs.append(job_data)
                    except Exception as e:
                        logger.warning(f"[CV-Library] Error parsing card: {e}")
                        continue

            except httpx.HTTPError as e:
                logger.error(f"[CV-Library] HTTP Error: {e}")

        return all_jobs

    async def get_job_details(self, raw_job: Dict[str, Any]) -> Dict[str, Any]:
        return raw_job

    async def normalize(self, raw_job: Dict[str, Any]) -> Dict[str, Any]:
        loc_raw = raw_job.get("location_raw", "")
        city, country = loc_raw, "United Kingdom"

        return {
            "id": raw_job.get("id", ""),
            "title": raw_job.get("title", ""),
            "company": raw_job.get("company", ""),
            "country": country,
            "state": None,
            "city": city,
            "remote": "remote" in loc_raw.lower(),
            "employment_type": None,
            "salary_min": None,
            "salary_max": None,
            "currency": "GBP",
            "job_url": raw_job.get("job_url", ""),
            "apply_url": raw_job.get("job_url", ""),
            "description": "",
            "posted_date": raw_job.get("date", ""),
            "open_time": raw_job.get("date", ""),
            "close_time": None,
            "source": self.source_name,
            "company_logo": None,
            "applicants": None
        }
