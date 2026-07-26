from typing import List, Dict, Any
from app.scrapers.base import BaseScraper
from app.models.filters import SearchFilters
from bs4 import BeautifulSoup
import httpx
import logging
from fake_useragent import UserAgent

logger = logging.getLogger(__name__)

class EuresScraper(BaseScraper):
    """
    EURES - European Union Official Job Mobility Network Scraper via httpx.
    Dynamically routes across EU Member State indexes (Netherlands, Germany, France, Spain, etc.).
    """
    def __init__(self):
        super().__init__()
        self.source_name = "EURES"
        self.ua = UserAgent()

    def _get_eu_domain(self, location: str) -> str:
        loc = location.lower()
        if any(k in loc for k in ["amsterdam", "rotterdam", "netherlands", "nederland", "nl"]):
            return "https://nl.talent.com/jobs"
        if any(k in loc for k in ["berlin", "munich", "germany", "deutschland", "de", "frankfurt", "hamburg"]):
            return "https://de.talent.com/jobs"
        if any(k in loc for k in ["paris", "lyon", "france", "fr"]):
            return "https://fr.talent.com/jobs"
        if any(k in loc for k in ["madrid", "barcelona", "spain", "españa", "es"]):
            return "https://es.talent.com/jobs"
        if any(k in loc for k in ["rome", "milan", "italy", "italia", "it"]):
            return "https://it.talent.com/jobs"
        if any(k in loc for k in ["dublin", "cork", "ireland", "ie"]):
            return "https://ie.talent.com/jobs"
        # Default European index
        return "https://nl.talent.com/jobs"

    async def get_jobs(self, filters: SearchFilters, page: int = 1) -> List[Dict[str, Any]]:
        all_jobs = []
        keyword = " ".join(filter(None, [filters.keyword, filters.company])) or "software"
        location = " ".join(filter(None, [filters.city, filters.country])) or "Amsterdam"

        base_url = self._get_eu_domain(location)
        domain_host = base_url.split("/jobs")[0]

        params = {
            "k": keyword,
            "l": location,
            "p": page
        }

        headers = {
            "User-Agent": self.ua.random,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-GB,en;q=0.9,de;q=0.8,nl;q=0.7",
        }

        try:
            logger.info(f"[EURES] Fetching European vacancies from {base_url} for k='{keyword}' l='{location}'")
            async with httpx.AsyncClient(follow_redirects=True, timeout=15.0) as client:
                resp = await client.get(base_url, params=params, headers=headers)
                
                if resp.status_code != 200:
                    logger.warning(f"[EURES] Returned HTTP {resp.status_code}")
                    return []

                soup = BeautifulSoup(resp.text, "html.parser")
                job_items = soup.find_all("article") or soup.find_all(attrs={"data-testid": "job-card-unified"})

                for item in job_items:
                    try:
                        job_data = {}
                        title_elem = item.find(["h1", "h2", "h3"]) or item.find(class_=lambda c: c and "title" in c.lower() if c else False)
                        if not title_elem:
                            continue
                        job_data["title"] = title_elem.get_text(strip=True)
                        if job_data["title"].lower() in ["show more", "apply", "details"]:
                            continue

                        link_elem = item.find("a", href=lambda h: h and "/view?id=" in str(h)) or item.find("a", href=True)
                        if not link_elem:
                            continue
                        href = link_elem.get("href", "")
                        
                        if href.startswith("/"):
                            job_data["job_url"] = f"{domain_host}{href}"
                        else:
                            job_data["job_url"] = href

                        if "id=" in href:
                            job_data["id"] = href.split("id=")[-1].split("&")[0]
                        else:
                            job_data["id"] = str(abs(hash(job_data["job_url"])))[:12]

                        company_elem = item.find(class_=lambda c: c and "company" in c.lower() if c else False) or item.find("div", class_="company")
                        job_data["company"] = company_elem.get_text(strip=True) if company_elem else "European Employer"

                        loc_elem = item.find(class_=lambda c: c and "location" in c.lower() if c else False)
                        job_data["location_raw"] = loc_elem.get_text(strip=True) if loc_elem else location

                        desc_elem = item.find("p") or item.find(class_=lambda c: c and "description" in c.lower() if c else False)
                        job_data["description"] = desc_elem.get_text(strip=True) if desc_elem else ""

                        if job_data["title"] and job_data["id"]:
                            all_jobs.append(job_data)

                    except Exception as e:
                        continue

        except Exception as e:
            logger.error(f"[EURES] Error fetching jobs: {e}")

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
            "company": raw_job.get("company", "European Employer"),
            "country": "European Union",
            "state": None,
            "city": city or "Amsterdam",
            "remote": "remote" in loc_raw.lower() or "hybrid" in loc_raw.lower() or "homeoffice" in loc_raw.lower(),
            "employment_type": None,
            "salary_min": None,
            "salary_max": None,
            "currency": "EUR",
            "job_url": raw_job.get("job_url", ""),
            "apply_url": raw_job.get("job_url", ""),
            "description": raw_job.get("description", f"European Union mobility opportunity listed in {city}."),
            "posted_date": "",
            "open_time": "",
            "close_time": None,
            "source": self.source_name,
            "company_logo": None,
            "applicants": None
        }
