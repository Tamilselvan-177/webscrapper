from typing import List, Dict, Any
from app.scrapers.base import BaseScraper
from app.models.filters import SearchFilters
from bs4 import BeautifulSoup
import httpx
import logging
import urllib.parse
from fake_useragent import UserAgent

logger = logging.getLogger(__name__)

class IndeedScraper(BaseScraper):
    """
    Indeed Scraper (also powers Monster, Workopolis via affiliate mappings).
    Uses HTTP client with intelligent fallback to Adzuna REST API if Cloudflare/Akamai blocks direct access.
    """
    def __init__(self):
        super().__init__()
        self.source_name = "Indeed"
        self.base_url = "https://www.indeed.com/jobs"
        self.ua = UserAgent()

    async def get_jobs(self, filters: SearchFilters, page: int = 1) -> List[Dict[str, Any]]:
        all_jobs = []
        start = (page - 1) * 10

        keyword = " ".join(filter(None, [filters.keyword, filters.company])) or "developer"
        location = " ".join(filter(None, [filters.city, filters.country])) or "London"

        url = f"{self.base_url}?q={urllib.parse.quote(keyword)}&l={urllib.parse.quote(location)}&start={start}"

        try:
            logger.info(f"[Indeed] Fetching via HTTP: {url}")
            headers = {
                'User-Agent': self.ua.random,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
            }
            async with httpx.AsyncClient(timeout=8.0, follow_redirects=True, headers=headers) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, "html.parser")
                    job_cards = soup.find_all("div", class_="job_seen_beacon") or soup.find_all("div", attrs={"data-jk": True}) or soup.find_all("div", class_=lambda c: c and "job_seen_beacon" in c)
                    
                    for card in job_cards:
                        try:
                            job_data = {}
                            jk = card.get("data-jk") or card.find(attrs={"data-jk": True})
                            if hasattr(jk, "get"):
                                jk = jk.get("data-jk", "")
                            job_data["id"] = str(jk) if jk else ""

                            title_elem = card.find("h2", class_="jobTitle") or card.find("span", {"title": True})
                            job_data["title"] = title_elem.get_text(strip=True) if title_elem else ""

                            company_elem = card.find("span", attrs={"data-testid": "company-name"}) or card.find(class_="companyName")
                            job_data["company"] = company_elem.get_text(strip=True) if company_elem else "Indeed Partner"

                            loc_elem = card.find("div", attrs={"data-testid": "text-location"}) or card.find(class_="companyLocation")
                            job_data["location_raw"] = loc_elem.get_text(strip=True) if loc_elem else location

                            date_elem = card.find("span", attrs={"data-testid": "myJobsStateDate"}) or card.find(class_="date")
                            job_data["date"] = date_elem.get_text(strip=True) if date_elem else ""

                            if job_data["id"]:
                                job_data["job_url"] = f"https://www.indeed.com/viewjob?jk={job_data['id']}"
                            else:
                                link = card.find("a", href=True)
                                job_data["job_url"] = "https://www.indeed.com" + link["href"] if link else ""

                            if job_data.get("title") and job_data.get("id"):
                                all_jobs.append(job_data)
                        except Exception:
                            continue
        except Exception as e:
            logger.warning(f"[Indeed] Direct HTTP error: {e}")

        # Intelligent Fallback if perimeter defense blocked direct access
        if not all_jobs:
            logger.info(f"[Indeed] Using API fallback for {keyword} in {location}")
            try:
                import os
                app_id = os.getenv("ADZUNA_APP_ID", "71b0f298")
                app_key = os.getenv("ADZUNA_APP_KEY", "8f2ce8aef294190f8892004471d453d4")
                country_code = "gb" if "uk" in location.lower() or "london" in location.lower() or not location else "us"
                api_url = f"https://api.adzuna.com/v1/api/jobs/{country_code}/search/{page}?app_id={app_id}&app_key={app_key}&what={urllib.parse.quote(keyword)}&results_per_page=15"
                if location and country_code != location.lower():
                    api_url += f"&where={urllib.parse.quote(location)}"
                
                async with httpx.AsyncClient(timeout=8.0) as client:
                    resp = await client.get(api_url)
                    if resp.status_code == 200:
                        data = resp.json()
                        for item in data.get("results", []):
                            all_jobs.append({
                                "id": str(item.get("id", "")),
                                "title": item.get("title", ""),
                                "company": item.get("company", {}).get("display_name", "Indeed Employer") if isinstance(item.get("company"), dict) else str(item.get("company", "Indeed Employer")),
                                "location_raw": item.get("location", {}).get("display_name", location) if isinstance(item.get("location"), dict) else location,
                                "date": item.get("created", "").split("T")[0] if item.get("created") else "",
                                "job_url": item.get("redirect_url", ""),
                                "description": item.get("description", "")
                            })
            except Exception as e:
                logger.error(f"[Indeed] Fallback API error: {e}")

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
            "id": str(raw_job.get("id", "")),
            "title": raw_job.get("title", ""),
            "company": raw_job.get("company", "Indeed Employer"),
            "country": country or "United Kingdom",
            "state": None,
            "city": city or "London",
            "remote": "remote" in loc_raw.lower(),
            "employment_type": None,
            "salary_min": None,
            "salary_max": None,
            "currency": "GBP" if country == "United Kingdom" or "UK" in str(country) else "USD",
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
