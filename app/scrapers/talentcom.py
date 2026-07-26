from typing import List, Dict, Any
from app.scrapers.base import BaseScraper
from app.models.filters import SearchFilters
from bs4 import BeautifulSoup
import httpx
import logging
from fake_useragent import UserAgent

logger = logging.getLogger(__name__)

class TalentComScraper(BaseScraper):
    """
    Talent.com - Global Job Aggregator.
    Scrapes job listings across UK, Europe, US, and Global markets.
    """
    def __init__(self):
        super().__init__()
        self.source_name = "Talent.com"
        self.base_url = "https://uk.talent.com/jobs"
        self.ua = UserAgent()

    async def get_jobs(self, filters: SearchFilters, page: int = 1) -> List[Dict[str, Any]]:
        all_jobs = []
        keyword = " ".join(filter(None, [filters.keyword, filters.company])) or "developer"
        location = " ".join(filter(None, [filters.city, filters.country])) or "London"

        params = {
            "k": keyword,
            "l": location,
            "p": page
        }

        headers = {
            "User-Agent": self.ua.random,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

        try:
            logger.info(f"[Talent.com] Fetching jobs for k='{keyword}' l='{location}'")
            async with httpx.AsyncClient(follow_redirects=True, timeout=15.0) as client:
                resp = await client.get(self.base_url, params=params, headers=headers)
                
                if resp.status_code != 200:
                    logger.warning(f"[Talent.com] Returned HTTP {resp.status_code}")
                    return []

                soup = BeautifulSoup(resp.text, "html.parser")
                job_items = soup.find_all("article") or soup.find_all(attrs={"data-testid": "job-card-unified"})

                logger.info(f"[Talent.com] Found {len(job_items)} job cards")

                for item in job_items:
                    try:
                        job_data = {}
                        
                        # Title
                        title_elem = item.find(["h1", "h2", "h3"]) or item.find(class_=lambda c: c and "title" in c.lower() if c else False)
                        if not title_elem:
                            continue
                        job_data["title"] = title_elem.get_text(strip=True)
                        if job_data["title"].lower() in ["show more", "apply", "details"]:
                            continue

                        # Link
                        link_elem = item.find("a", href=lambda h: h and "/view?id=" in str(h)) or item.find("a", href=True)
                        if not link_elem:
                            continue
                        href = link_elem.get("href", "")
                        
                        if href.startswith("/"):
                            job_data["job_url"] = f"https://uk.talent.com{href}"
                        else:
                            job_data["job_url"] = href

                        # Extract ID
                        if "id=" in href:
                            job_data["id"] = href.split("id=")[-1].split("&")[0]
                        else:
                            job_data["id"] = str(abs(hash(job_data["job_url"])))[:12]

                        # Company
                        company_elem = item.find(class_=lambda c: c and "company" in c.lower() if c else False) or item.find("div", class_="company")
                        job_data["company"] = company_elem.get_text(strip=True) if company_elem else "Employer"

                        # Location
                        loc_elem = item.find(class_=lambda c: c and "location" in c.lower() if c else False)
                        job_data["location_raw"] = loc_elem.get_text(strip=True) if loc_elem else location

                        # Salary / Snippet
                        desc_elem = item.find("p") or item.find(class_=lambda c: c and "description" in c.lower() if c else False)
                        job_data["description"] = desc_elem.get_text(strip=True) if desc_elem else ""

                        if job_data["title"] and job_data["id"]:
                            all_jobs.append(job_data)

                    except Exception as e:
                        logger.warning(f"[Talent.com] Error parsing card: {e}")
                        continue

        except Exception as e:
            logger.error(f"[Talent.com] Error fetching jobs: {e}")

        return all_jobs

    async def get_job_details(self, raw_job: Dict[str, Any]) -> Dict[str, Any]:
        return raw_job

    async def normalize(self, raw_job: Dict[str, Any]) -> Dict[str, Any]:
        loc_raw = raw_job.get("location_raw", "")
        city = loc_raw
        country = "United Kingdom"

        if "," in loc_raw:
            parts = loc_raw.split(",")
            city = parts[0].strip()

        return {
            "id": raw_job.get("id", ""),
            "title": raw_job.get("title", ""),
            "company": raw_job.get("company", "Employer"),
            "country": country,
            "state": None,
            "city": city,
            "remote": "remote" in loc_raw.lower(),
            "employment_type": None,
            "salary_min": None,
            "salary_max": None,
            "currency": "GBP" if "£" in raw_job.get("description", "") else None,
            "job_url": raw_job.get("job_url", ""),
            "apply_url": raw_job.get("job_url", ""),
            "description": raw_job.get("description", ""),
            "posted_date": "",
            "open_time": "",
            "close_time": None,
            "source": self.source_name,
            "company_logo": None,
            "applicants": None
        }
