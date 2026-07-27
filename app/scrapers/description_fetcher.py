"""
description_fetcher.py
~~~~~~~~~~~~~~~~~~~~~~~
Shared utility for fetching FULL job descriptions from job detail pages.

Most job boards show a truncated snippet on the listing page with a
"Show more" / "See full description" button that requires JavaScript.
This module fetches the detail URL via plain HTTP and extracts the
complete description using site-specific CSS selectors.

Usage in any scraper's get_job_details():

    from app.scrapers.description_fetcher import fetch_full_description

    async def get_job_details(self, raw_job):
        return await fetch_full_description(raw_job, source="indeed")
"""

import re
import asyncio
import logging
import httpx
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)
_ua = UserAgent()

# ---------------------------------------------------------------------------
# Site-specific CSS selectors (most specific first, generic fallback last)
# ---------------------------------------------------------------------------
SELECTORS: Dict[str, List[str]] = {
    "indeed": [
        "#jobDescriptionText",
        '[class*="jobsearch-jobDescriptionText"]',
        '[id*="jobDescription"]',
        ".job-description",
    ],
    "adzuna": [
        ".job-description",
        '[class*="description"]',
        '[id*="description"]',
        "article.job-listing",
        "main article",
    ],
    "glassdoor": [
        '[class*="JobDetails_jobDescription"]',
        '[data-test="description"]',
        ".jobDescriptionContent",
        "#JobDescriptionContainer",
        '[class*="desc"]',
    ],
    "totaljobs": [
        ".job-description",
        '[class*="job-description"]',
        "#job-description",
        "article .content",
        ".description-container",
    ],
    "stepstone": [
        '[data-testid="job-description"]',
        ".at-section-text-description",
        '[class*="jobAd__content"]',
        ".js-job-description",
    ],
    "reed": [
        "#job-description",
        '[itemprop="description"]',
        ".description",
        ".job-details__description",
    ],
    "seek": [
        '[data-automation="jobAdDetails"]',
        '[class*="jobAdDetails"]',
        ".jobDetailsContainer",
        ".job-content",
    ],
    "jora": [
        ".job-description",
        '[class*="description"]',
        "article",
    ],
    "jobrapido": [
        ".job_description",
        ".description",
        '[class*="description"]',
    ],
    "irishjobs": [
        '[class*="description"]',
        '[data-testid="job-description"]',
        ".job-description",
        "article",
    ],
    "jobsireland": [
        ".job-description",
        '[class*="description"]',
        "main article",
    ],
    "workopolis": [
        ".job-description",
        '[class*="description"]',
        ".content",
    ],
    "michaelpage": [
        ".job-description",
        '[class*="content"]',
        ".richtext",
    ],
    "randstad": [
        ".job-description",
        '[class*="description"]',
        ".content-block",
    ],
    "hays": [
        ".job-description",
        ".content-block",
        '[class*="description"]',
    ],
    "linkedin": [
        ".description__text",
        ".jobs-description__content",
        '[class*="description__text"]',
        ".job-view-layout",
    ],
    "monster": [
        "#JobDescription",
        ".job-description",
        '[class*="description"]',
    ],
    # Generic fallback applied when no site-specific selector matches
    "__fallback__": [
        '[class*="description"]',
        '[id*="description"]',
        '[class*="job-detail"]',
        '[id*="job-detail"]',
        "article",
        "main",
    ],
}


def _clean_html(html_or_text: str) -> str:
    """
    Convert HTML fragment to clean plain text suitable for ATS analysis.
    Removes buttons, scripts, "Show more" artifacts, and normalises whitespace.
    """
    if not html_or_text:
        return ""
    text = html_or_text
    # Remove button / script / style elements
    text = re.sub(r"<button[^>]*>.*?</button>", "", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", text, flags=re.IGNORECASE | re.DOTALL)
    # Structural tags → newlines
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</(p|div|h[1-6]|li|tr|section|article)>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<li[^>]*>", "• ", text, flags=re.IGNORECASE)
    # Strip remaining tags
    text = re.sub(r"<[^>]+>", "", text)
    # HTML entities
    replacements = {
        "&amp;": "&", "&lt;": "<", "&gt;": ">",
        "&nbsp;": " ", "&#39;": "'", "&quot;": '"',
        "&ndash;": "–", "&mdash;": "—", "&bull;": "•",
    }
    for entity, char in replacements.items():
        text = text.replace(entity, char)
    # Remove "Show more" / "See more" button text
    text = re.sub(r"\b(Show|See|Read)\s+(more|less|full description|job details?)\b", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\b(Expand|Collapse|See full description)\b", "", text, flags=re.IGNORECASE)
    # Collapse whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def _extract_from_soup(soup: BeautifulSoup, source: str) -> Optional[str]:
    """Try site-specific selectors, then generic fallback."""
    selectors = SELECTORS.get(source.lower(), []) + SELECTORS["__fallback__"]
    
    for selector in selectors:
        try:
            elem = soup.select_one(selector)
            if elem:
                text = _clean_html(str(elem))
                if len(text) > 200:  # Must be a real description, not a nav/header
                    return text
        except Exception:
            continue
_browser_sem = None
def _get_browser_sem():
    global _browser_sem
    if _browser_sem is None:
        _browser_sem = asyncio.Semaphore(3)  # Max 3 concurrent headless browsers
    return _browser_sem


async def fetch_with_browser(url: str, selector: Optional[str] = None, source: str = "") -> str:
    """
    Launches headless Chromium with Playwright Stealth evasions to bypass bot detection (Cloudflare, etc.)
    and extracts full job description text from rendered pages (SEEK, Jora, etc.).
    """
    if not url or url == "#":
        return ""
    try:
        from playwright.async_api import async_playwright
        from playwright_stealth import Stealth
    except ImportError:
        logger.warning("[DescFetcher:browser] Playwright or playwright_stealth not installed.")
        return ""

    try:
        sem = _get_browser_sem()
        async with sem:
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=True,
                    args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
                )
                try:
                    context = await browser.new_context(
                        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                        viewport={"width": 1280, "height": 800},
                        locale="en-AU" if source.lower() in ("seek", "jora", "careerone", "workforceaustralia") else "en-US"
                    )
                    page = await context.new_page()
                    await Stealth().apply_stealth_async(page)
                    
                    logger.info(f"[DescFetcher:browser] Navigating to {url}")
                    await page.goto(url, timeout=18000, wait_until="domcontentloaded")
                    await asyncio.sleep(1.5)  # Wait for JS hydration and Cloudflare challenge resolution
                    
                    html = await page.content()
                    soup = BeautifulSoup(html, "html.parser")
                    
                    if selector:
                        elem = soup.select_one(selector)
                        if elem:
                            return _clean_html(str(elem))
                    
                    full_text = _extract_from_soup(soup, source)
                    if not full_text and source.lower() in ("seek", "jora", "careerone", "workforceaustralia"):
                        elem = soup.select_one('[data-automation="jobAdDetails"]') or soup.select_one('.jobDetailsContainer') or soup.select_one('.job-description')
                        if elem:
                            full_text = _clean_html(str(elem))
                    
                    return full_text or ""
                finally:
                    await browser.close()
    except Exception as e:
        logger.debug(f"[DescFetcher:browser] Error fetching {url}: {e}")
        return ""


async def fetch_full_description(
    raw_job: Dict[str, Any],
    source: str = "",
    min_length: int = 300,
) -> Dict[str, Any]:
    """
    Fetch the full job description from the job detail page.
    Automatically uses headless browser stealth for Cloudflare protected portals (SEEK, Jora, etc.)
    or when standard HTTP requests encounter perimeter defense blocks.
    """
    existing_desc = (raw_job.get("description") or "").strip()
    is_truncated = existing_desc.endswith("...") or existing_desc.endswith("…")
    
    if len(existing_desc) >= min_length and not is_truncated:
        return raw_job

    job_url = raw_job.get("job_url") or raw_job.get("apply_url") or ""
    if not job_url or job_url == "#":
        return raw_job

    # For SEEK, Jora, CareerOne, WorkforceAustralia, always use headless browser due to Cloudflare / 403 blocks
    if source.lower() in ("seek", "jora", "careerone", "workforceaustralia"):
        selector = '[data-automation="jobAdDetails"]' if source.lower() == "seek" else None
        full_text = await fetch_with_browser(job_url, selector=selector, source=source)
        if full_text and len(full_text) > len(existing_desc):
            logger.info(f"[DescFetcher:{source}] Fetched full description via browser ({len(full_text)} chars)")
            raw_job["description"] = full_text
        return raw_job

    headers = {
        "User-Agent": _ua.random,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-GB,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Cache-Control": "no-cache",
    }

    try:
        async with httpx.AsyncClient(
            timeout=10.0,
            follow_redirects=True,
            headers=headers,
        ) as client:
            resp = await client.get(job_url)
            if resp.status_code in (403, 401, 429, 503):
                logger.debug(f"[DescFetcher:{source}] HTTP {resp.status_code} blocked. Falling back to browser stealth.")
                full_text = await fetch_with_browser(job_url, source=source)
                if full_text and len(full_text) > len(existing_desc):
                    raw_job["description"] = full_text
                return raw_job

            if resp.status_code != 200:
                logger.debug(f"[DescFetcher:{source}] HTTP {resp.status_code} for {job_url}")
                return raw_job

            soup = BeautifulSoup(resp.text, "html.parser")
            full_text = _extract_from_soup(soup, source)

            if full_text and len(full_text) > len(existing_desc):
                logger.info(
                    f"[DescFetcher:{source}] Fetched full description "
                    f"({len(full_text)} chars) from {job_url}"
                )
                raw_job["description"] = full_text
            else:
                logger.debug(f"[DescFetcher:{source}] No text > 200 chars found via HTTP. Trying browser.")
                full_text = await fetch_with_browser(job_url, source=source)
                if full_text and len(full_text) > len(existing_desc):
                    raw_job["description"] = full_text

    except httpx.TimeoutException:
        logger.debug(f"[DescFetcher:{source}] Timeout fetching {job_url}")
    except Exception as e:
        logger.debug(f"[DescFetcher:{source}] Error fetching {job_url}: {e}")

    return raw_job
