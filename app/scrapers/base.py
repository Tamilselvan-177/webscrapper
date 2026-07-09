from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import logging
from pydantic import ValidationError
from app.models.job import JobSchema
from app.models.filters import SearchFilters
from app.core.http_client import HTTPClient

logger = logging.getLogger(__name__)

class ScraperFetchError(Exception):
    pass

class ScraperValidationError(Exception):
    pass

class BaseScraper(ABC):
    """
    Abstract base class for all job scrapers implementing the Template Method Pattern.
    """
    
    def __init__(self):
        self.source_name: str = "base"
        self.base_url: str = ""
        # Initialize client here or in subclasses
        self.client: Optional[HTTPClient] = None

    async def search(self, filters: SearchFilters) -> List[JobSchema]:
        """
        Template method orchestrating the search:
        fetches raw jobs, iterates, normalizes, validates, and handles errors.
        """
        normalized_jobs = []
        try:
            logger.info(f"[{self.source_name}] Starting search for company '{filters.company}'")
            raw_jobs = await self.get_jobs(filters)
            
            for raw_job in raw_jobs:
                try:
                    # Some ATS require fetching details separately
                    job_detail = await self.get_job_details(raw_job)
                    
                    # Normalize to dict
                    job_dict = await self.normalize(job_detail)
                    
                    # Validate strictly using Pydantic JobSchema
                    validated_job = JobSchema.model_validate(job_dict)
                    normalized_jobs.append(validated_job)
                    
                except ValidationError as ve:
                    logger.error(f"[{self.source_name}] Schema validation failed for job: {ve}")
                except Exception as e:
                    logger.error(f"[{self.source_name}] Error processing job: {e}")
                    
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning(f"[{self.source_name}] Company not found (404). Returning empty list.")
                return []
            logger.error(f"[{self.source_name}] HTTP Error: {e}")
            raise ScraperFetchError(f"Failed to fetch jobs from {self.source_name}: {e}")
        except Exception as e:
            logger.error(f"[{self.source_name}] Unexpected Error: {e}")
            raise ScraperFetchError(f"Failed to fetch jobs from {self.source_name}: {e}")
            
        logger.info(f"[{self.source_name}] Successfully validated {len(normalized_jobs)} jobs.")
        return normalized_jobs

    @abstractmethod
    async def get_jobs(self, filters: SearchFilters, page: int = 1) -> List[Dict[str, Any]]:
        """
        Fetches the raw job listings from the source.
        Returns a list of raw job dictionaries.
        """
        pass

    @abstractmethod
    async def get_job_details(self, raw_job: Dict[str, Any]) -> Dict[str, Any]:
        """
        Fetches detailed information if required, or just returns raw_job if details are included.
        """
        pass

    @abstractmethod
    async def normalize(self, raw_job: Dict[str, Any]) -> Dict[str, Any]:
        """
        Converts the raw source data into a dictionary matching the JobSchema fields.
        """
        pass

    async def close(self):
        if self.client:
            await self.client.close()
