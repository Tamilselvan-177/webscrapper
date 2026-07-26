from typing import List, Dict, Any
from app.scrapers.base import BaseScraper
from app.models.filters import SearchFilters
from bs4 import BeautifulSoup
import httpx
import logging
from fake_useragent import UserAgent

logger = logging.getLogger(__name__)

class MichaelPageScraper(BaseScraper):
    """
    Michael Page Careers - UK & Global Recruitment Agency Scraper via httpx.
    """
    def __init__(self):
        super().__init__()
        self.source_name = "Michael Page Careers"
        self.base_url = "https://www.michaelpage.co.uk/jobs"
        self.ua = UserAgent()

    async def get_jobs(self, filters: SearchFilters, page: int = 1) -> List[Dict[str, Any]]:
        all_jobs = []
        keyword = " ".join(filter(None, [filters.keyword, filters.company])) or "developer"
        location = " ".join(filter(None, [filters.city, filters.country])) or "London"

        params = {
            "search": keyword,
            "location": location
        }
        if page > 1:
            params["page"] = page - 1 # 0-indexed on Michael Page

        headers = {
            "User-Agent": self.ua.random,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-GB,en;q=0.9",
        }

        try:
            logger.info(f"[Michael Page] Fetching jobs for search='{keyword}' location='{location}'")
            async with httpx.AsyncClient(follow_redirects=True, timeout=15.0) as client:
                resp = await client.get(self.base_url, params=params, headers=headers)
                
                if resp.status_code != 200:
                    logger.warning(f"[Michael Page] Returned HTTP {resp.status_code}")
                    return []

                soup = BeautifulSoup(resp.text, "html.parser")
                
                # Find all job links (Michael Page URLs: /job-detail/title/ref/jn-...)
                job_links = soup.find_all("a", href=lambda h: h and "/job-detail/" in h and "/ref/" in h)

                seen_urls = set()
                for link in job_links:
                    try:
                        href = link["href"]
                        if href in seen_urls:
                            continue
                        seen_urls.add(href)

                        job_data = {}
                        title = link.get_text(strip=True)
                        if len(title) < 3 or title.lower() in ["apply", "save", "view"]:
                            continue
                        job_data["title"] = title

                        job_data["job_url"] = href if href.startswith("http") else f"https://www.michaelpage.co.uk{href}"
                        
                        # Extract ID from ref (e.g. /ref/jn-072026-7069954)
                        parts = href.split("/ref/")
                        if len(parts) > 1:
                            job_data["id"] = parts[1].strip("/")
                        else:
                            job_data["id"] = str(abs(hash(job_data["job_url"])))[:10]

                        job_data["company"] = "Michael Page Client"
                        job_data["location_raw"] = location
                        job_data["salary_text"] = ""

                        # Check if card wrapper has salary/location details
                        card = link.find_parent("li") or link.find_parent("div", class_=lambda c: c and "job" in c.lower())
                        if card:
                            loc_elem = card.find(class_=lambda x: x and ("location" in x.lower() or "city" in x.lower()))
                            if loc_elem:
                                job_data["location_raw"] = loc_elem.get_text(strip=True)
                            sal_elem = card.find(class_=lambda x: x and ("salary" in x.lower() or "rate" in x.lower())) or card.find(string=lambda s: s and "£" in s)
                            if sal_elem:
                                job_data["salary_text"] = sal_elem.get_text(strip=True) if hasattr(sal_elem, "get_text") else str(sal_elem)

                        if job_data["title"] and job_data["id"]:
                            all_jobs.append(job_data)
                    except Exception as e:
                        continue

        except Exception as e:
            logger.error(f"[Michael Page] Error fetching jobs: {e}")

        return all_jobs

    async def get_job_details(self, raw_job: Dict[str, Any]) -> Dict[str, Any]:
        return raw_job

    async def normalize(self, raw_job: Dict[str, Any]) -> Dict[str, Any]:
        loc_raw = raw_job.get("location_raw", "")
        city = loc_raw
        if "," in loc_raw:
            city = loc_raw.split(",")[0].strip()

        return {
            "id": str(raw_job.get("id", "")),
            "title": raw_job.get("title", ""),
            "company": raw_job.get("company", "Michael Page Client"),
            "country": "United Kingdom",
            "state": None,
            "city": city or "United Kingdom",
            "remote": "remote" in loc_raw.lower(),
            "employment_type": None,
            "salary_min": None,
            "salary_max": None,
            "currency": "GBP" if "£" in raw_job.get("salary_text", "") else None,
            "job_url": raw_job.get("job_url", ""),
            "apply_url": raw_job.get("job_url", ""),
            "description": raw_job.get("salary_text", f"Position recruited by Michael Page in {city}."),
            "posted_date": "",
            "open_time": "",
            "close_time": None,
            "source": self.source_name,
            "company_logo": None,
            "applicants": None
        }
