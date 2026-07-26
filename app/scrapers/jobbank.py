from typing import List, Dict, Any
from app.scrapers.base import BaseScraper
from app.models.filters import SearchFilters
from bs4 import BeautifulSoup
import httpx
import logging
from fake_useragent import UserAgent

logger = logging.getLogger(__name__)

class JobBankScraper(BaseScraper):
    """
    Job Bank Canada (Government Portal) - HTML Scraper via httpx.
    Scrapes official Canadian government job vacancies.
    """
    def __init__(self):
        super().__init__()
        self.source_name = "Job Bank Canada"
        self.base_url = "https://www.jobbank.gc.ca/jobsearch/jobsearch"
        self.ua = UserAgent()

    async def get_jobs(self, filters: SearchFilters, page: int = 1) -> List[Dict[str, Any]]:
        all_jobs = []
        keyword = " ".join(filter(None, [filters.keyword, filters.company])) or "developer"
        location = " ".join(filter(None, [filters.city, filters.country])) or ""

        params = {
            "searchstring": keyword,
            "locationstring": location,
            "page": page,
            "sort": "M" # Sort by match/date
        }

        headers = {
            "User-Agent": self.ua.random,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-CA,en;q=0.9",
        }

        try:
            logger.info(f"[JobBank] Fetching jobs for keyword='{keyword}' location='{location}'")
            async with httpx.AsyncClient(follow_redirects=True, timeout=15.0) as client:
                resp = await client.get(self.base_url, params=params, headers=headers)
                
                if resp.status_code != 200:
                    logger.warning(f"[JobBank] Returned HTTP {resp.status_code}")
                    return []

                soup = BeautifulSoup(resp.text, "html.parser")
                job_items = soup.find_all("a", class_="resultJobItem") or soup.find_all("article")

                logger.info(f"[JobBank] Found {len(job_items)} job cards")

                for item in job_items:
                    try:
                        job_data = {}
                        
                        # Title
                        title_elem = item.find("span", class_="noctitle") or item.find("h3") or item.find("span", class_="title")
                        if not title_elem:
                            continue
                        job_data["title"] = title_elem.get_text(strip=True)

                        # URL & ID
                        href = item.get("href", "") if item.name == "a" else (item.find("a", href=True)["href"] if item.find("a", href=True) else "")
                        if not href:
                            continue
                        if href.startswith("/"):
                            job_data["job_url"] = f"https://www.jobbank.gc.ca{href}"
                        else:
                            job_data["job_url"] = href
                            
                        # Extract ID from posting URL (e.g., /jobposting/49943593)
                        parts = href.split("jobposting/")
                        if len(parts) > 1:
                            job_data["id"] = parts[1].split(";")[0].split("?")[0]
                        else:
                            job_data["id"] = str(abs(hash(job_data["job_url"])))[:10]

                        # Company
                        company_elem = item.find("li", class_="business") or item.find("ul", class_="list-unstyled")
                        if company_elem:
                            job_data["company"] = company_elem.get_text(strip=True)
                        else:
                            job_data["company"] = "Canadian Employer"

                        # Location
                        loc_elem = item.find("li", class_="location") or item.find(string=lambda s: s and "(" in s and ")" in s)
                        job_data["location_raw"] = loc_elem.get_text(strip=True) if hasattr(loc_elem, "get_text") else str(loc_elem or "Canada")

                        # Salary
                        salary_elem = item.find("li", class_="salary") or item.find(string=lambda s: s and "$" in s)
                        job_data["salary_text"] = salary_elem.get_text(strip=True) if hasattr(salary_elem, "get_text") else (str(salary_elem) if salary_elem else "")

                        # Date
                        date_elem = item.find("li", class_="date") or item.find("time")
                        job_data["date"] = date_elem.get_text(strip=True) if hasattr(date_elem, "get_text") else ""

                        if job_data["title"] and job_data["id"]:
                            all_jobs.append(job_data)

                    except Exception as e:
                        logger.warning(f"[JobBank] Error parsing card: {e}")
                        continue

        except Exception as e:
            logger.error(f"[JobBank] Error fetching jobs: {e}")

        return all_jobs

    async def get_job_details(self, raw_job: Dict[str, Any]) -> Dict[str, Any]:
        return raw_job

    async def normalize(self, raw_job: Dict[str, Any]) -> Dict[str, Any]:
        loc_raw = raw_job.get("location_raw", "")
        city = loc_raw
        country = "Canada"

        if "(" in loc_raw and ")" in loc_raw:
            parts = loc_raw.split("(")
            city = parts[0].strip()

        return {
            "id": raw_job.get("id", ""),
            "title": raw_job.get("title", ""),
            "company": raw_job.get("company", "Canadian Employer"),
            "country": country,
            "state": None,
            "city": city,
            "remote": "remote" in loc_raw.lower(),
            "employment_type": None,
            "salary_min": None,
            "salary_max": None,
            "currency": "CAD" if "$" in raw_job.get("salary_text", "") else None,
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
