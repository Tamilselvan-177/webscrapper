from typing import List, Dict, Any
from app.scrapers.base import BaseScraper
from app.models.filters import SearchFilters
import logging
import httpx
from bs4 import BeautifulSoup
from fake_useragent import UserAgent

logger = logging.getLogger(__name__)

class JobrapidoScraper(BaseScraper):
    """
    Jobrapido - Global Job Aggregator Scraper via HTTP client.
    """
    def __init__(self):
        super().__init__()
        self.source_name = "Jobrapido"
        self.base_url = "https://uk.jobrapido.com/"
        self.ua = UserAgent()

    async def get_jobs(self, filters: SearchFilters, page: int = 1) -> List[Dict[str, Any]]:
        all_jobs = []
        keyword = " ".join(filter(None, [filters.keyword, filters.company])) or "developer"
        location = " ".join(filter(None, [filters.city, filters.country])) or "London"

        url = f"{self.base_url}?w={keyword}&l={location}&r=auto"
        if page > 1:
            url += f"&p={page}"

        try:
            logger.info(f"[Jobrapido] Fetching via HTTP: {url}")
            headers = {
                "User-Agent": self.ua.random,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-GB,en;q=0.5",
            }
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True, headers=headers) as client:
                resp = await client.get(url)
                if resp.status_code != 200:
                    logger.warning(f"[Jobrapido] HTTP status {resp.status_code}")
                    return []
                html = resp.text

            soup = BeautifulSoup(html, "html.parser")
            
            # Find all job links with /jobpreview/ or /job in href
            job_links = soup.find_all("a", href=lambda h: h and ("/jobpreview/" in h or "/job/" in h) and not any(k in h for k in ["/blog", "/support", "/login", "/signup", "/direct-employers", "javascript"]))

            seen_urls = set()
            for link in job_links:
                try:
                    href = link["href"]
                    if href in seen_urls or "google" in href.lower() or "[[advert" in href:
                        continue
                    seen_urls.add(href)

                    job_data = {}
                    title = link.get_text(strip=True)
                    for prefix in ["Open job preview for:", "Job preview:", "Preview:"]:
                        if title.startswith(prefix):
                            title = title[len(prefix):].strip()
                    if not title or len(title) < 3 or "advert" in title.lower():
                        continue
                    job_data["title"] = title

                    job_data["job_url"] = href if href.startswith("http") else f"https://uk.jobrapido.com{href}"
                    
                    if "/jobpreview/" in href:
                        job_data["id"] = href.split("/jobpreview/")[1].split("?")[0].strip("/")
                    else:
                        job_data["id"] = str(abs(hash(job_data["job_url"])))[:10]

                    job_data["company"] = "Jobrapido Partner"
                    job_data["location_raw"] = location
                    job_data["description"] = ""

                    card = link.find_parent("div", class_=lambda c: c and any(k in c.lower() for k in ["result", "item", "card", "advert"]))
                    if card:
                        comp_el = card.find(class_=lambda x: x and "company" in x.lower())
                        if comp_el and len(comp_el.get_text(strip=True)) > 1:
                            job_data["company"] = comp_el.get_text(strip=True)
                        desc_el = card.find(class_=lambda x: x and ("snippet" in x.lower() or "description" in x.lower())) or card.find("p")
                        if desc_el and len(desc_el.get_text(strip=True)) > 5:
                            job_data["description"] = desc_el.get_text(strip=True)

                    if job_data["title"] and job_data["id"]:
                        all_jobs.append(job_data)
                except Exception:
                    continue
        except Exception as e:
            logger.error(f"[Jobrapido] Error fetching jobs: {e}")

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
            "company": raw_job.get("company", "Jobrapido Partner"),
            "country": "United Kingdom",
            "state": None,
            "city": city or "London",
            "remote": "remote" in loc_raw.lower(),
            "employment_type": None,
            "salary_min": None,
            "salary_max": None,
            "currency": "GBP",
            "job_url": raw_job.get("job_url", ""),
            "apply_url": raw_job.get("job_url", ""),
            "description": raw_job.get("description", f"Position aggregated by Jobrapido in {city}."),
            "posted_date": "",
            "open_time": "",
            "close_time": None,
            "source": self.source_name,
            "company_logo": None,
            "applicants": None
        }
