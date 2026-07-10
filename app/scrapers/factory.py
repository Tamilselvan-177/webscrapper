from app.scrapers.base import BaseScraper
from app.scrapers.greenhouse import GreenhouseScraper
from app.scrapers.lever import LeverScraper
from app.scrapers.smartrecruiters import SmartRecruitersScraper
from app.scrapers.personio import PersonioScraper
from app.scrapers.ashby import AshbyScraper
from app.scrapers.linkedin import LinkedInScraper

def get_scraper(source: str) -> BaseScraper:
    """
    Scraper Factory.
    Dynamically returns the correct scraper instance based on the source name.
    """
    scrapers = {
        "greenhouse": GreenhouseScraper,
        "lever": LeverScraper,
        "smartrecruiters": SmartRecruitersScraper,
        "personio": PersonioScraper,
        "ashby": AshbyScraper,
        "linkedin": LinkedInScraper,
        "global": LinkedInScraper
    }
    
    source_key = source.lower()
    if source_key not in scrapers:
        raise ValueError(f"Unsupported source: {source}")
        
    return scrapers[source_key]()
