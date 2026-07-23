from typing import List, Dict, Any
from app.scrapers.base import BaseScraper
from app.models.filters import SearchFilters
from bs4 import BeautifulSoup
import httpx
import logging
from fake_useragent import UserAgent

logger = logging.getLogger(__name__)

class IndeedScraper(BaseScraper):
    def __init__(self):
        super().__init__()
        self.source_name = "Indeed"
        self.base_url = "https://www.indeed.com/jobs"
        self.ua = UserAgent()

    async def _get_headers(self) -> dict:
        return {
            'User-Agent': self.ua.random,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
        }

    async def get_jobs(self, filters: SearchFilters, page: int = 1) -> List[Dict[str, Any]]:
        all_jobs = []
        start = (page - 1) * 10

        keyword = " ".join(filter(None, [filters.keyword, filters.company]))
        location = " ".join(filter(None, [filters.city, filters.country]))

        params = {
            "q": keyword or "jobs",
            "l": location or "",
            "start": start
        }

        try:
            from app.core.browser_client import BrowserClient
            import asyncio
            browser_client = BrowserClient(executable_path=None)
            
            page_obj = await browser_client.get_page()
            logger.info(f"[Indeed] Navigating to {self.base_url}?q={keyword}&l={location}&start={start}")
            
            # Construct URL
            url = f"{self.base_url}?q={keyword or 'jobs'}&l={location or ''}&start={start}"
            
            await page_obj.goto(url, wait_until="networkidle", timeout=20000)
            await asyncio.sleep(2) # wait for jobs to render
            
            html = await page_obj.content()
            await browser_client.close()
            
            soup = BeautifulSoup(html, "html.parser")

            # Indeed uses data-jk attribute for job key
            job_cards = soup.find_all("div", class_="job_seen_beacon")
            if not job_cards:
                job_cards = soup.find_all("div", attrs={"data-jk": True})
            if not job_cards:
                # fallback
                job_cards = soup.find_all("div", class_=lambda c: c and "job_seen_beacon" in c)

            logger.info(f"[Indeed] Found {len(job_cards)} job cards via Browser")

            for card in job_cards:
                try:
                    job_data = {}
                    # Job key (ID)
                    jk = card.get("data-jk") or card.find(attrs={"data-jk": True})
                    if hasattr(jk, "get"):
                        jk = jk.get("data-jk", "")
                    job_data["id"] = str(jk) if jk else ""

                    # Title
                    title_elem = card.find("h2", class_="jobTitle") or card.find("span", {"title": True})
                    job_data["title"] = title_elem.get_text(strip=True) if title_elem else ""

                    # Company
                    company_elem = card.find("span", attrs={"data-testid": "company-name"}) or card.find(class_="companyName")
                    job_data["company"] = company_elem.get_text(strip=True) if company_elem else ""

                    # Location
                    loc_elem = card.find("div", attrs={"data-testid": "text-location"}) or card.find(class_="companyLocation")
                    job_data["location_raw"] = loc_elem.get_text(strip=True) if loc_elem else ""

                    # Date
                    date_elem = card.find("span", attrs={"data-testid": "myJobsStateDate"}) or card.find(class_="date")
                    job_data["date"] = date_elem.get_text(strip=True) if date_elem else ""

                    # Job URL
                    if job_data["id"]:
                        job_data["job_url"] = f"https://www.indeed.com/viewjob?jk={job_data['id']}"
                    else:
                        link = card.find("a", href=True)
                        job_data["job_url"] = "https://www.indeed.com" + link["href"] if link else ""

                    if job_data.get("title") and job_data.get("id"):
                        all_jobs.append(job_data)

                except Exception as e:
                    logger.warning(f"[Indeed] Error parsing card: {e}")
                    continue

        except Exception as e:
            logger.error(f"[Indeed] Browser Error: {e}")

        return all_jobs

    async def get_job_details(self, raw_job: Dict[str, Any]) -> Dict[str, Any]:
        return raw_job

    async def normalize(self, raw_job: Dict[str, Any]) -> Dict[str, Any]:
        loc_raw = raw_job.get("location_raw", "")
        city, country = loc_raw, None
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
            "remote": "remote" in loc_raw.lower(),
            "employment_type": None,
            "salary_min": None,
            "salary_max": None,
            "currency": None,
            "job_url": raw_job.get("job_url", ""),
            "apply_url": raw_job.get("job_url", ""),
            "description": raw_job.get("description", ""),
            "posted_date": raw_job.get("date", ""),
            "open_time": raw_job.get("date", ""),
            "close_time": None,
            "source": self.source_name,
            "company_logo": None,
            "applicants": None
        }
