from typing import List, Dict, Any
from app.scrapers.base import BaseScraper
from app.models.filters import SearchFilters
from app.core.browser_client import BrowserClient
from bs4 import BeautifulSoup
import logging
import asyncio

logger = logging.getLogger(__name__)

class SeekScraper(BaseScraper):
    """
    SEEK Australia - HTML scraper via Headless Browser (Obscura).
    Bypasses Cloudflare protection by rendering the page.
    """
    def __init__(self):
        super().__init__()
        self.source_name = "SEEK"
        self.browser_client = BrowserClient(executable_path=None)

    async def get_jobs(self, filters: SearchFilters, page: int = 1) -> List[Dict[str, Any]]:
        all_jobs = []
        keyword = "-".join(filter(None, [filters.keyword, filters.company])).replace(" ", "-").lower()
        location = (filters.city or "").replace(" ", "-").lower()

        if keyword and location:
            url = f"https://www.seek.com.au/{keyword}-jobs/in-{location}"
        elif keyword:
            url = f"https://www.seek.com.au/{keyword}-jobs"
        else:
            url = "https://www.seek.com.au/jobs"
            
        if page > 1:
            url += f"?page={page}"

        try:
            page_obj = await self.browser_client.get_page()
            logger.info(f"[SEEK] Navigating to {url}")
            await page_obj.goto(url, wait_until="networkidle", timeout=20000)
            
            # Wait a moment for dynamic jobs to load
            await asyncio.sleep(2)
            
            html = await page_obj.content()
            await self.browser_client.close()

            soup = BeautifulSoup(html, "html.parser")

            job_cards = soup.find_all("article", attrs={"data-automation": "normalJob"})
            if not job_cards:
                job_cards = soup.find_all("article", attrs={"data-card-type": "JobCard"})
            if not job_cards:
                job_cards = soup.find_all("article")

            logger.info(f"[SEEK] Found {len(job_cards)} job cards via Browser")

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
                    job_data["company"] = company_elem.get_text(strip=True) if company_elem else ""

                    loc_elem = card.find(attrs={"data-automation": "jobLocation"}) or card.find(attrs={"data-automation": "jobArea"})
                    job_data["location_raw"] = loc_elem.get_text(strip=True) if loc_elem else location

                    date_elem = card.find(attrs={"data-automation": "jobListingDate"}) or card.find("time")
                    job_data["date"] = date_elem.get_text(strip=True) if date_elem else ""

                    salary_elem = card.find(attrs={"data-automation": "jobSalary"})
                    job_data["salary_text"] = salary_elem.get_text(strip=True) if salary_elem else ""

                    if job_data.get("title") and job_data.get("id"):
                        all_jobs.append(job_data)

                except Exception as e:
                    logger.warning(f"[SEEK] Error parsing card: {e}")
                    continue

        except Exception as e:
            logger.error(f"[SEEK] Browser Error: {e}")

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
