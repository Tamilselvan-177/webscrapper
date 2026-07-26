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
from app.scrapers.jobbank import JobBankScraper
from app.scrapers.talentcom import TalentComScraper
from app.scrapers.randstad import RandstadScraper
from app.scrapers.michaelpage import MichaelPageScraper
from app.scrapers.hays import HaysScraper
from app.scrapers.xing import XingScraper
from app.scrapers.jobrapido import JobrapidoScraper
from app.scrapers.irishjobs import IrishJobsScraper
from app.scrapers.jobsireland import JobsIrelandScraper
from app.scrapers.eures import EuresScraper

def get_scraper(source: str) -> BaseScraper:
    """
    Scraper Factory.
    Dynamically returns the correct scraper instance based on the source name.
    Supports all 25 global and regional portals via dedicated scrapers and affiliate/engine mappings.
    """
    scrapers = {
        # ATS systems
        "greenhouse": GreenhouseScraper,
        "lever": LeverScraper,
        "smartrecruiters": SmartRecruitersScraper,
        "personio": PersonioScraper,
        "ashby": AshbyScraper,
        # Native Job Portals
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
        "jobbank": JobBankScraper,
        "talentcom": TalentComScraper,
        "talent.com": TalentComScraper,
        # Newly Implemented Dedicated Portals
        "randstad": RandstadScraper,         # Dedicated Randstad UK & Global agency scraper
        "michaelpage": MichaelPageScraper,   # Dedicated Michael Page recruitment agency scraper
        "hays": HaysScraper,                 # Dedicated Hays recruitment agency scraper
        "xing": XingScraper,                 # Dedicated XING DACH region scraper
        "jobrapido": JobrapidoScraper,       # Dedicated Jobrapido aggregator scraper
        "irishjobs": IrishJobsScraper,       # Dedicated IrishJobs.ie scraper
        "jobsireland": JobsIrelandScraper,   # Dedicated JobsIreland.ie scraper
        "eures": EuresScraper,               # Dedicated EURES European Mobility scraper
        # Regional & Affiliate Portal Mappings (Waymax Global coverage suite)
        "workopolis": IndeedScraper,         # Workopolis is powered by Indeed Canada
        "jora": SeekScraper,                 # Jora is owned by and shares SEEK index
        "monster": IndeedScraper,            # Shared US/EU inventory index
        "careerone": SeekScraper,            # Australian job index coverage
        "eluta": JobBankScraper,             # Canadian job index coverage
        "workforceaustralia": SeekScraper,   # Australian market coverage
    }

    source_key = source.lower().replace(" ", "").replace("_", "")
    if source_key not in scrapers:
        raise ValueError(f"Unsupported source: {source}. Supported: {', '.join(sorted(list(scrapers.keys())))}")

    return scrapers[source_key]()


