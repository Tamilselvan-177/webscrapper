from app.scrapers.base import BaseScraper
from app.scrapers.greenhouse import GreenhouseScraper
from app.scrapers.lever import LeverScraper
from app.scrapers.smartrecruiters import SmartRecruitersScraper
from app.scrapers.personio import PersonioScraper
from app.scrapers.ashby import AshbyScraper
from app.scrapers.linkedin import LinkedInScraper
from app.scrapers.adzuna import AdzunaScraper
from app.scrapers.reed import ReedScraper
from app.scrapers.indeed import IndeedScraper
from app.scrapers.seek import SeekScraper
from app.scrapers.totaljobs import TotaljobsScraper
from app.scrapers.cvlibrary import CvLibraryScraper
from app.scrapers.careerjet import CareerjetScraper
from app.scrapers.stepstone import StepstoneScraper
from app.scrapers.glassdoor import GlassdoorScraper

def get_scraper(source: str) -> BaseScraper:
    """
    Scraper Factory.
    Dynamically returns the correct scraper instance based on the source name.
    """
    scrapers = {
        # ATS systems
        "greenhouse": GreenhouseScraper,
        "lever": LeverScraper,
        "smartrecruiters": SmartRecruitersScraper,
        "personio": PersonioScraper,
        "ashby": AshbyScraper,
        # Job Portals
        "linkedin": LinkedInScraper,
        "global": LinkedInScraper,
        "adzuna": AdzunaScraper,
        "reed": ReedScraper,
        "indeed": IndeedScraper,
        "seek": SeekScraper,
        "totaljobs": TotaljobsScraper,
        "cvlibrary": CvLibraryScraper,
        "careerjet": CareerjetScraper,
        "stepstone": StepstoneScraper,
        "glassdoor": GlassdoorScraper,
    }

    source_key = source.lower()
    if source_key not in scrapers:
        raise ValueError(f"Unsupported source: {source}")

    return scrapers[source_key]()

