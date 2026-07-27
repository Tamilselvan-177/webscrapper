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
    return None


async def fetch_full_description(
    raw_job: Dict[str, Any],
    source: str = "",
    min_length: int = 300,
) -> Dict[str, Any]:
    """
    Fetch the full job description from the job detail page.

    If the raw_job already has a description longer than `min_length`
    characters we skip the fetch (it's already complete).

    Returns the same raw_job dict with `description` updated in-place.
    """
    existing_desc = (raw_job.get("description") or "").strip()
    
    is_truncated = existing_desc.endswith("...") or existing_desc.endswith("…")
    
    # Already long enough and doesn't look like a cut-off snippet — no need to re-fetch
    if len(existing_desc) >= min_length and not is_truncated:
        return raw_job

    job_url = raw_job.get("job_url") or raw_job.get("apply_url") or ""
    if not job_url or job_url == "#":
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
                logger.debug(
                    f"[DescFetcher:{source}] No better description found at {job_url}"
                )

    except httpx.TimeoutException:
        logger.debug(f"[DescFetcher:{source}] Timeout fetching {job_url}")
    except Exception as e:
        logger.debug(f"[DescFetcher:{source}] Error fetching {job_url}: {e}")

    return raw_job
