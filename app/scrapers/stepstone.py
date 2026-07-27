from typing import List, Dict, Any
from app.scrapers.base import BaseScraper
from app.models.filters import SearchFilters
from bs4 import BeautifulSoup
import httpx
import logging
import urllib.parse
from fake_useragent import UserAgent

logger = logging.getLogger(__name__)


class StepstoneScraper(BaseScraper):
    """
    StepStone Scraper (Germany & European market).

    Strategy:
    1. Try direct HTTP with proxy + realistic headers (German locale)
    2. If blocked by Akamai Bot Manager → use anti-detect browser with proxy
    3. Browser waits for Akamai challenge to resolve (up to 20s)
    """

    def __init__(self):
        super().__init__()
        self.source_name = "StepStone"
        self.base_url = "https://www.stepstone.de/jobs/"
        self.ua = UserAgent()

    async def get_jobs(self, filters: SearchFilters, page: int = 1) -> List[Dict[str, Any]]:
        keyword = (filters.keyword or filters.company or "developer").replace(" ", "-").lower()
        location = (filters.city or filters.country or "Berlin").replace(" ", "-").lower()

        url = f"https://www.stepstone.de/jobs/{keyword}/in-{location}"
        if page > 1:
            url += f"?page={page}"

        # ── Step 1: Try direct HTTP with proxy ──
        logger.info(f"[StepStone] Attempting HTTP: {url}")
        all_jobs = await self._fetch_via_http(url, location)

        if all_jobs:
            logger.info(f"[StepStone] HTTP returned {len(all_jobs)} jobs")
            return all_jobs

        # ── Step 2: Anti-detect browser fallback ──
        logger.info(f"[StepStone] HTTP blocked/empty. Trying anti-detect browser: {url}")
        all_jobs = await self._fetch_via_browser(url, location)

        return all_jobs

    async def _fetch_via_http(self, url: str, location: str) -> List[Dict[str, Any]]:
        """Attempt to fetch jobs via direct HTTP with proxy support."""
        try:
            from app.core.proxy_client import ProxyHTTPClient
            client = ProxyHTTPClient(timeout=12.0)
            resp = await client.get(
                url,
                headers={
                    "Accept-Language": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7",
                },
            )
            await client.close()

            if resp.status_code != 200:
                logger.info(f"[StepStone] HTTP got {resp.status_code}")
                return []

            # Check for Akamai challenge page
            body_lower = resp.text[:3000].lower()
            if any(m in body_lower for m in ["access denied", "ak_bmsc", "reference #", "bm-verify", "akamai"]):
                logger.info("[StepStone] Akamai challenge detected in HTTP response")
                return []

            return self._parse_jobs(resp.text, location)

        except Exception as e:
            logger.warning(f"[StepStone] HTTP error: {e}")
            return []

    async def _fetch_via_browser(self, url: str, location: str) -> List[Dict[str, Any]]:
        """Fetch jobs using anti-detect browser with Akamai challenge waiting."""
        try:
            from app.core.anti_detect_browser import AntiDetectBrowser

            async with AntiDetectBrowser(locale="de-DE", timeout=30000) as browser:
                html, challenge = await browser.fetch_page(url, challenge_wait=25)

                if not html:
                    logger.warning("[StepStone] Browser returned no HTML")
                    return []

                if challenge:
                    logger.warning(f"[StepStone] Browser still blocked: {challenge}")
                    return []

                return self._parse_jobs(html, location)

        except Exception as e:
            logger.error(f"[StepStone] Browser error: {e}")
            return []

    def _parse_jobs(self, html: str, location: str) -> List[Dict[str, Any]]:
        """Parse StepStone job listings from HTML."""
        jobs = []
        soup = BeautifulSoup(html, "html.parser")

        job_cards = (
            soup.find_all("article", attrs={"data-at": "job-item"})
            or soup.find_all("article")
        )

        for card in job_cards:
            try:
                job_data = {}

                # Title
                title_elem = card.find("h2") or card.find("a", attrs={"data-at": "job-item-title"})
                if not title_elem:
                    continue
                job_data["title"] = title_elem.get_text(strip=True)

                # URL
                link_elem = card.find("a", href=True)
                if link_elem:
                    href = link_elem["href"]
                    job_data["job_url"] = href if href.startswith("http") else f"https://www.stepstone.de{href}"
                else:
                    job_data["job_url"] = ""
                job_data["id"] = str(abs(hash(job_data.get("job_url", ""))))[:10]

                # Company
                company_elem = card.find(attrs={"data-at": "job-item-company-name"}) or card.find(
                    "span", class_=lambda c: c and "company" in c.lower()
                )
                job_data["company"] = company_elem.get_text(strip=True) if company_elem else "StepStone Employer"

                # Location
                loc_elem = card.find(attrs={"data-at": "job-item-location"}) or card.find(
                    "span", class_=lambda c: c and "location" in c.lower()
                )
                job_data["location_raw"] = loc_elem.get_text(strip=True) if loc_elem else location

                # Salary
                salary_elem = card.find("span", class_=lambda c: c and "salary" in c.lower() or "gehalt" in c.lower())
                job_data["salary"] = salary_elem.get_text(strip=True) if salary_elem else ""

                # Date
                date_elem = card.find("span", class_=lambda c: c and "date" in c.lower() or "posted" in c.lower())
                job_data["date"] = date_elem.get_text(strip=True) if date_elem else ""

                if job_data.get("title") and job_data.get("job_url"):
                    jobs.append(job_data)

            except Exception as e:
                logger.debug(f"[StepStone] Error parsing card: {e}")
                continue

        return jobs

    async def get_job_details(self, raw_job: Dict[str, Any]) -> Dict[str, Any]:
        return raw_job

    async def normalize(self, raw_job: Dict[str, Any]) -> Dict[str, Any]:
        loc_raw = raw_job.get("location_raw", "")
        city, country = loc_raw, "Germany"
        if "," in loc_raw:
            parts = loc_raw.split(",")
            city = parts[0].strip()
            country = parts[-1].strip()

        return {
            "id": str(raw_job.get("id", "")),
            "title": raw_job.get("title", ""),
            "company": raw_job.get("company", "StepStone Partner"),
            "country": country,
            "state": None,
            "city": city or "Berlin",
            "remote": "remote" in loc_raw.lower() or "homeoffice" in loc_raw.lower(),
            "employment_type": None,
            "salary_min": None,
            "salary_max": None,
            "currency": "EUR" if country == "Germany" else "GBP",
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
