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
    Indeed Scraper (also powers Monster, Workopolis via factory mappings).

    Strategy:
    1. Try direct HTTP with proxy + realistic headers
    2. If blocked by Cloudflare Turnstile → use anti-detect browser with proxy
    3. Browser waits for Cloudflare challenge to resolve (up to 30s)
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

        # ── Step 1: Try direct HTTP with proxy ──
        logger.info(f"[Indeed] Attempting HTTP: {url}")
        all_jobs = await self._fetch_via_http(url, location)

        if all_jobs:
            logger.info(f"[Indeed] HTTP returned {len(all_jobs)} jobs")
            return all_jobs

        # ── Step 2: Anti-detect browser fallback ──
        logger.info(f"[Indeed] HTTP blocked/empty. Trying anti-detect browser: {url}")
        all_jobs = await self._fetch_via_browser(url, location, keyword)

        return all_jobs

    async def _fetch_via_http(self, url: str, location: str) -> List[Dict[str, Any]]:
        """Attempt to fetch jobs via direct HTTP with proxy support."""
        jobs = []
        try:
            from app.core.proxy_client import ProxyHTTPClient
            client = ProxyHTTPClient(timeout=12.0)
            resp = await client.get(url)
            await client.close()

            if resp.status_code != 200:
                logger.info(f"[Indeed] HTTP got {resp.status_code}")
                return []

            # Check for Cloudflare challenge page
            body_lower = resp.text[:3000].lower()
            if any(m in body_lower for m in ["just a moment", "cf-turnstile", "checking your browser", "__cf_chl"]):
                logger.info("[Indeed] Cloudflare challenge detected in HTTP response")
                return []

            return self._parse_jobs(resp.text, location)

        except Exception as e:
            logger.warning(f"[Indeed] HTTP error: {e}")
            return []

    async def _fetch_via_browser(self, url: str, location: str, keyword: str) -> List[Dict[str, Any]]:
        """Fetch jobs using anti-detect browser with Cloudflare challenge waiting."""
        try:
            from app.core.anti_detect_browser import AntiDetectBrowser

            async with AntiDetectBrowser(locale="en-GB", timeout=30000) as browser:
                html, challenge = await browser.fetch_page(url, challenge_wait=35)

                if challenge:
                    logger.warning(f"[Indeed] Browser still blocked: {challenge}")
                    # Try alternative: search on uk.indeed.com
                    alt_url = url.replace("indeed.com", "uk.indeed.com")
                    html, challenge = await browser.fetch_page(alt_url, challenge_wait=35)

                if not html:
                    logger.warning("[Indeed] Browser returned no HTML")
                    return []

                if challenge:
                    logger.warning(f"[Indeed] Browser still blocked after retry: {challenge}")
                    return []

                return self._parse_jobs(html, location)

        except Exception as e:
            logger.error(f"[Indeed] Browser error: {e}")
            return []

    def _parse_jobs(self, html: str, location: str) -> List[Dict[str, Any]]:
        """Parse Indeed job listings from HTML."""
        jobs = []
        soup = BeautifulSoup(html, "html.parser")

        job_cards = (
            soup.find_all("div", class_="job_seen_beacon")
            or soup.find_all("div", attrs={"data-jk": True})
            or soup.find_all("div", class_=lambda c: c and "job_seen_beacon" in c)
        )

        for card in job_cards:
            try:
                job_data = {}

                # Extract job key (jk)
                jk = card.get("data-jk") or ""
                if not jk:
                    jk_elem = card.find(attrs={"data-jk": True})
                    if jk_elem:
                        jk = jk_elem.get("data-jk", "")
                job_data["id"] = str(jk) if jk else ""

                # Title
                title_elem = card.find("h2", class_="jobTitle") or card.find("span", {"title": True})
                job_data["title"] = title_elem.get_text(strip=True) if title_elem else ""

                # Company
                company_elem = card.find("span", attrs={"data-testid": "company-name"}) or card.find(class_="companyName")
                job_data["company"] = company_elem.get_text(strip=True) if company_elem else "Indeed Partner"

                # Location
                loc_elem = card.find("div", attrs={"data-testid": "text-location"}) or card.find(class_="companyLocation")
                job_data["location_raw"] = loc_elem.get_text(strip=True) if loc_elem else location

                # Date
                date_elem = card.find("span", attrs={"data-testid": "myJobsStateDate"}) or card.find(class_="date")
                job_data["date"] = date_elem.get_text(strip=True) if date_elem else ""

                # URL
                if job_data["id"]:
                    job_data["job_url"] = f"https://www.indeed.com/viewjob?jk={job_data['id']}"
                else:
                    link = card.find("a", href=True)
                    if link:
                        href = link["href"]
                        job_data["job_url"] = href if href.startswith("http") else f"https://www.indeed.com{href}"
                    else:
                        job_data["job_url"] = ""

                # Salary
                salary_elem = card.find("div", class_="salary-snippet-container") or card.find("span", class_="salaryText")
                job_data["salary"] = salary_elem.get_text(strip=True) if salary_elem else ""

                if job_data.get("title") and (job_data.get("id") or job_data.get("job_url")):
                    jobs.append(job_data)

            except Exception as e:
                logger.debug(f"[Indeed] Error parsing card: {e}")
                continue

        return jobs

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
            "applicants": None,
        }
