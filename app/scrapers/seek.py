from typing import List, Dict, Any
from app.scrapers.base import BaseScraper
from app.models.filters import SearchFilters
from bs4 import BeautifulSoup
import httpx
import logging
from fake_useragent import UserAgent

logger = logging.getLogger(__name__)

class SeekScraper(BaseScraper):
    """
    SEEK Australia - HTML scraper.
    Their internal API is protected so we scrape the HTML search results page.
    """
    def __init__(self):
        super().__init__()
        self.source_name = "SEEK"
        self.ua = UserAgent()

    async def _get_headers(self) -> dict:
        return {
            'User-Agent': self.ua.random,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-AU,en;q=0.9',
            'Referer': 'https://www.seek.com.au/',
        }

    async def get_jobs(self, filters: SearchFilters, page: int = 1) -> List[Dict[str, Any]]:
        all_jobs = []
        keyword = "-".join(filter(None, [filters.keyword, filters.company])).replace(" ", "-").lower()
        location = (filters.city or "").replace(" ", "-").lower()

        # Build SEEK URL: seek.com.au/{keyword}-jobs/in-{location}
        if keyword and location:
            url = f"https://www.seek.com.au/{keyword}-jobs/in-{location}"
        elif keyword:
            url = f"https://www.seek.com.au/{keyword}-jobs"
        else:
            url = "https://www.seek.com.au/jobs"

        params = {"page": page}

        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            try:
                response = await client.get(url, params=params, headers=await self._get_headers())
                response.raise_for_status()
                soup = BeautifulSoup(response.text, "html.parser")

                # SEEK uses data-automation attributes
                job_cards = soup.find_all("article", attrs={"data-automation": "normalJob"})
                if not job_cards:
                    job_cards = soup.find_all("article", attrs={"data-card-type": "JobCard"})
                if not job_cards:
                    # fallback: any article with a job link
                    job_cards = soup.find_all("article")

                logger.info(f"[SEEK] Found {len(job_cards)} job cards in HTML")

                for card in job_cards:
                    try:
                        job_data = {}

                        # Title & URL
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

                        # Extract job ID from URL
                        parts = job_data["job_url"].split("/")
                        job_data["id"] = parts[-1] if parts else ""

                        # Company
                        company_elem = card.find(attrs={"data-automation": "jobCompany"}) or card.find("a", attrs={"data-automation": "jobListingDate"})
                        if not company_elem:
                            company_elem = card.find("span", class_=lambda c: c and "company" in c.lower() if c else False)
                        job_data["company"] = company_elem.get_text(strip=True) if company_elem else ""

                        # Location
                        loc_elem = card.find(attrs={"data-automation": "jobLocation"}) or card.find(attrs={"data-automation": "jobArea"})
                        job_data["location_raw"] = loc_elem.get_text(strip=True) if loc_elem else location

                        # Date
                        date_elem = card.find(attrs={"data-automation": "jobListingDate"}) or card.find("time")
                        job_data["date"] = date_elem.get_text(strip=True) if date_elem else ""

                        # Salary
                        salary_elem = card.find(attrs={"data-automation": "jobSalary"})
                        job_data["salary_text"] = salary_elem.get_text(strip=True) if salary_elem else ""

                        if job_data.get("title") and job_data.get("id"):
                            all_jobs.append(job_data)

                    except Exception as e:
                        logger.warning(f"[SEEK] Error parsing card: {e}")
                        continue

            except httpx.HTTPError as e:
                logger.error(f"[SEEK] HTTP Error: {e}")
            except Exception as e:
                logger.error(f"[SEEK] Error: {e}")

        return all_jobs

    async def get_job_details(self, raw_job: Dict[str, Any]) -> Dict[str, Any]:
        return raw_job

    async def normalize(self, raw_job: Dict[str, Any]) -> Dict[str, Any]:
        loc_raw = raw_job.get("location_raw", "")
        city, country = loc_raw, "Australia"
        if "," in loc_raw:
            parts = loc_raw.split(",")
            city = parts[0].strip()

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
            "currency": "AUD",
            "job_url": raw_job.get("job_url", ""),
            "apply_url": raw_job.get("job_url", ""),
            "description": raw_job.get("salary_text", ""),
            "posted_date": raw_job.get("date", ""),
            "open_time": raw_job.get("date", ""),
            "close_time": None,
            "source": self.source_name,
            "company_logo": None,
            "applicants": None
        }
