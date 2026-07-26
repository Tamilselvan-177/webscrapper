from typing import List, Dict, Any
from app.scrapers.base import BaseScraper
from app.models.filters import SearchFilters
from bs4 import BeautifulSoup
import httpx
import logging
from fake_useragent import UserAgent

logger = logging.getLogger(__name__)

class RandstadScraper(BaseScraper):
    """
    Randstad Careers - UK & Global Recruitment Agency Scraper via httpx.
    """
    def __init__(self):
        super().__init__()
        self.source_name = "Randstad Careers"
        self.base_url = "https://www.randstad.co.uk/jobs"
        self.ua = UserAgent()

    async def get_jobs(self, filters: SearchFilters, page: int = 1) -> List[Dict[str, Any]]:
        all_jobs = []
        keyword = "-".join(filter(None, [filters.keyword, filters.company])).replace(" ", "-").lower() or "developer"

        url = f"{self.base_url}/q-{keyword}/"
        params = {"page": page} if page > 1 else {}
        if filters.city:
            params["location"] = filters.city

        headers = {
            "User-Agent": self.ua.random,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-GB,en;q=0.9",
        }

        try:
            logger.info(f"[Randstad] Fetching {url} with params {params}")
            async with httpx.AsyncClient(follow_redirects=True, timeout=15.0) as client:
                resp = await client.get(url, params=params, headers=headers)
                
                if resp.status_code != 200:
                    logger.warning(f"[Randstad] Returned HTTP {resp.status_code}")
                    return []

                soup = BeautifulSoup(resp.text, "html.parser")
                
                # Find all job links with underscores (Randstad job URLs format: /jobs/title_city_id/)
                job_links = soup.find_all("a", href=lambda h: h and "/jobs/" in h and "_" in h)

                seen_urls = set()
                for link in job_links:
                    try:
                        href = link["href"]
                        if href in seen_urls or "show job details" in link.get_text(strip=True).lower():
                            continue
                        seen_urls.add(href)

                        job_data = {}
                        title = link.get_text(strip=True)
                        if len(title) < 3:
                            continue
                        job_data["title"] = title

                        job_data["job_url"] = href if href.startswith("http") else f"https://www.randstad.co.uk{href}"
                        
                        # Extract ID and City from URL (e.g. /jobs/avaloq-senior-developer_london_46723201/)
                        parts = href.rstrip("/").split("_")
                        if len(parts) >= 3:
                            job_data["id"] = parts[-1]
                            job_data["location_raw"] = parts[-2].capitalize()
                        else:
                            job_data["id"] = str(abs(hash(job_data["job_url"])))[:10]
                            job_data["location_raw"] = filters.city or "United Kingdom"

                        job_data["company"] = "Randstad UK Client"
                        job_data["salary_text"] = ""

                        if job_data["title"] and job_data["id"]:
                            all_jobs.append(job_data)
                    except Exception as e:
                        continue

        except Exception as e:
            logger.error(f"[Randstad] Error fetching jobs: {e}")

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
            "company": raw_job.get("company", "Randstad UK Client"),
            "country": "United Kingdom",
            "state": None,
            "city": city or "United Kingdom",
            "remote": "remote" in loc_raw.lower(),
            "employment_type": None,
            "salary_min": None,
            "salary_max": None,
            "currency": "GBP",
            "job_url": raw_job.get("job_url", ""),
            "apply_url": raw_job.get("job_url", ""),
            "description": f"Position recruited by Randstad UK in {city}.",
            "posted_date": "",
            "open_time": "",
            "close_time": None,
            "source": self.source_name,
            "company_logo": None,
            "applicants": None
        }
