from typing import List, Dict, Any
from app.scrapers.base import BaseScraper
from app.models.filters import SearchFilters
from bs4 import BeautifulSoup
import httpx
import logging
from fake_useragent import UserAgent

logger = logging.getLogger(__name__)

class XingScraper(BaseScraper):
    """
    XING Jobs - Germany & DACH Region Scraper via httpx.
    """
    def __init__(self):
        super().__init__()
        self.source_name = "XING Jobs"
        self.base_url = "https://www.xing.com/jobs/search"
        self.ua = UserAgent()

    async def get_jobs(self, filters: SearchFilters, page: int = 1) -> List[Dict[str, Any]]:
        all_jobs = []
        keyword = " ".join(filter(None, [filters.keyword, filters.company])) or "entwickler"
        location = " ".join(filter(None, [filters.city, filters.country])) or "Berlin"

        params = {
            "keywords": keyword,
            "location": location
        }
        if page > 1:
            params["page"] = page

        headers = {
            "User-Agent": self.ua.random,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
        }

        try:
            logger.info(f"[XING] Fetching jobs for keywords='{keyword}' location='{location}'")
            async with httpx.AsyncClient(follow_redirects=True, timeout=15.0) as client:
                resp = await client.get(self.base_url, params=params, headers=headers)
                
                if resp.status_code != 200:
                    logger.warning(f"[XING] Returned HTTP {resp.status_code}")
                    return []

                soup = BeautifulSoup(resp.text, "html.parser")
                
                # Iterate over article tags representing job cards
                cards = soup.find_all("article")
                if not cards:
                    cards = soup.find_all("div", class_=lambda c: c and "job" in c.lower() and "card" in c.lower())

                seen_urls = set()
                for c in cards:
                    try:
                        link = c.find("a", href=lambda h: h and "/jobs/" in h and not any(k in h for k in ["/search", "/directory", "/create", "/api"]))
                        if not link:
                            continue
                        href = link["href"].split("?")[0]
                        if href in seen_urls:
                            continue
                        seen_urls.add(href)

                        job_data = {}
                        # Extract title from h2/h3 or aria-label
                        title_elem = c.find(["h1", "h2", "h3", "h4"])
                        if title_elem and title_elem.get_text(strip=True):
                            title = title_elem.get_text(strip=True)
                        elif c.get("aria-label"):
                            title = c.get("aria-label").split(".")[0].replace("Click to open", "").replace("Klicke", "").strip()
                        else:
                            continue

                        if len(title) < 3:
                            continue
                        job_data["title"] = title
                        job_data["job_url"] = href if href.startswith("http") else f"https://www.xing.com{href}"
                        
                        # Extract ID from URL slug (e.g. /jobs/berlin-junior-fullstack-developer-156154540)
                        parts = href.rstrip("/").split("-")
                        if parts and parts[-1].isdigit():
                            job_data["id"] = parts[-1]
                        else:
                            job_data["id"] = str(abs(hash(job_data["job_url"])))[:10]

                        job_data["company"] = "XING Employer"
                        comp_elem = c.find("p") or c.find(class_=lambda x: x and ("company" in x.lower() or "employer" in x.lower()))
                        if comp_elem and len(comp_elem.get_text(strip=True)) > 2:
                            job_data["company"] = comp_elem.get_text(strip=True)[:50]

                        job_data["location_raw"] = location
                        job_data["salary_text"] = ""

                        if job_data["title"] and job_data["id"]:
                            all_jobs.append(job_data)
                    except Exception as e:
                        continue

        except Exception as e:
            logger.error(f"[XING] Error fetching jobs: {e}")

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
            "company": raw_job.get("company", "XING Employer"),
            "country": "Germany",
            "state": None,
            "city": city or "Berlin",
            "remote": "remote" in loc_raw.lower() or "homeoffice" in loc_raw.lower(),
            "employment_type": None,
            "salary_min": None,
            "salary_max": None,
            "currency": "EUR",
            "job_url": raw_job.get("job_url", ""),
            "apply_url": raw_job.get("job_url", ""),
            "description": f"Position listed on XING in {city}.",
            "posted_date": "",
            "open_time": "",
            "close_time": None,
            "source": self.source_name,
            "company_logo": None,
            "applicants": None
        }
