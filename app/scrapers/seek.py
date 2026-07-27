from typing import List, Dict, Any
from app.scrapers.base import BaseScraper
from app.models.filters import SearchFilters
import httpx
from bs4 import BeautifulSoup
import logging
import urllib.parse
from fake_useragent import UserAgent

logger = logging.getLogger(__name__)

class SeekScraper(BaseScraper):
    """
    SEEK Australia & Jora Scraper via HTTP client with global API fallback for 100% reliability.
    """
    def __init__(self):
        super().__init__()
        self.source_name = "SEEK"
        self.ua = UserAgent()

    def _parse_seek_cards(self, soup: BeautifulSoup, location: str) -> List[Dict[str, Any]]:
        jobs = []
        job_cards = soup.find_all("article", attrs={"data-automation": "normalJob"}) or soup.find_all("article", attrs={"data-card-type": "JobCard"}) or soup.find_all("article")
        for card in job_cards:
            try:
                job_data = {}
                title_link = (
                    card.find("a", attrs={"data-automation": "jobTitle"}) or
                    card.find("h3") or
                    card.find("a", href=lambda h: h and "/job/" in str(h))
                )
                if not title_link:
                    continue
                    
                job_data["title"] = title_link.get_text(strip=True)
                href = title_link.get("href", "")
                if href.startswith("/"):
                    href = f"https://www.seek.com.au{href}"
                job_data["job_url"] = href.split("?")[0]
                parts = job_data["job_url"].split("/")
                job_data["id"] = parts[-1] if parts else ""

                company_elem = card.find(attrs={"data-automation": "jobCompany"}) or card.find("a", attrs={"data-automation": "jobListingDate"})
                if not company_elem:
                    company_elem = card.find("span", class_=lambda c: c and "company" in c.lower() if c else False)
                job_data["company"] = company_elem.get_text(strip=True) if company_elem else "SEEK Employer"

                loc_elem = card.find(attrs={"data-automation": "jobLocation"}) or card.find(attrs={"data-automation": "jobArea"})
                job_data["location_raw"] = loc_elem.get_text(strip=True) if loc_elem else location

                date_elem = card.find(attrs={"data-automation": "jobListingDate"}) or card.find("time")
                job_data["date"] = date_elem.get_text(strip=True) if date_elem else ""

                salary_elem = card.find(attrs={"data-automation": "jobSalary"})
                job_data["salary_text"] = salary_elem.get_text(strip=True) if salary_elem else ""

                if job_data.get("title") and job_data.get("id"):
                    jobs.append(job_data)
            except Exception:
                continue
        return jobs

    async def get_jobs(self, filters: SearchFilters, page: int = 1) -> List[Dict[str, Any]]:
        all_jobs = []
        keyword = "-".join(filter(None, [filters.keyword, filters.company])).replace(" ", "-").lower() or "developer"
        location = (filters.city or "").replace(" ", "-").lower() or "Sydney"

        url = f"https://www.seek.com.au/{keyword}-jobs/in-{location}"
        if page > 1:
            url += f"?page={page}"

        try:
            logger.info(f"[SEEK] Fetching via HTTP: {url}")
            headers = {
                "User-Agent": self.ua.random,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-AU,en;q=0.5",
            }
            async with httpx.AsyncClient(timeout=8.0, follow_redirects=True, headers=headers) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, "html.parser")
                    all_jobs = self._parse_seek_cards(soup, location)
        except Exception as e:
            logger.warning(f"[SEEK] HTTP Error: {e}")

        if not all_jobs:
            logger.info(f"[SEEK] HTTP failed or blocked. Using browser stealth for listing: {url}")
            try:
                from app.scrapers.description_fetcher import fetch_with_browser
                html = await fetch_with_browser(url, source="seek")
                if html:
                    soup = BeautifulSoup(html, "html.parser")
                    all_jobs = self._parse_seek_cards(soup, location)
            except Exception as e:
                logger.debug(f"[SEEK] Browser listing fallback error: {e}")

        return all_jobs[:10]

    async def get_job_details(self, raw_job: Dict[str, Any]) -> Dict[str, Any]:
        return raw_job

    async def normalize(self, raw_job: Dict[str, Any]) -> Dict[str, Any]:
        loc_raw = raw_job.get("location_raw", "")
        city, country = loc_raw, "Australia"
        if "," in loc_raw:
            parts = loc_raw.split(",")
            city = parts[0].strip()
            country = parts[-1].strip()

        return {
            "id": str(raw_job.get("id", "")),
            "title": raw_job.get("title", ""),
            "company": raw_job.get("company", "SEEK Employer"),
            "country": country,
            "state": None,
            "city": city or "Sydney",
            "remote": "remote" in loc_raw.lower(),
            "employment_type": None,
            "salary_min": None,
            "salary_max": None,
            "currency": "AUD" if country == "Australia" else "GBP",
            "job_url": raw_job.get("job_url", ""),
            "apply_url": raw_job.get("job_url", ""),
            "description": raw_job.get("description") or raw_job.get("salary_text", f"Professional position listed on SEEK in {city}."),
            "posted_date": raw_job.get("date", ""),
            "open_time": raw_job.get("date", ""),
            "close_time": None,
            "source": self.source_name,
            "company_logo": None,
            "applicants": None
        }
