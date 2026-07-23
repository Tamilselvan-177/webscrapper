from fastapi import APIRouter, Query, Path, HTTPException
from typing import List, Optional, Dict, Any
from app.models.job import JobSchema
from app.models.filters import SearchFilters
from app.scrapers.factory import get_scraper

router = APIRouter()

@router.get("/jobs", response_model=List[JobSchema], summary="Search jobs across ATS sources")
async def search_jobs(
    source: str = Query(..., description="The source ATS to scrape (e.g. greenhouse, lever, smartrecruiters, personio, ashby)"),
    company: Optional[str] = Query(None, description="The company slug to search for (e.g. 'contentful' for Greenhouse)"),
    keyword: Optional[str] = Query(None, description="Search by keyword or job title"),
    country: Optional[str] = Query(None, description="Filter by country"),
    city: Optional[str] = Query(None, description="Filter by city"),
    remote: Optional[bool] = Query(None, description="Filter for remote jobs"),
    salary_min: Optional[float] = Query(None, description="Minimum salary"),
    employment_type: Optional[str] = Query(None, description="e.g. Full-time, Part-time"),
    page: int = Query(1, description="Pagination page (if supported by source)")
):
    """
    Scrape and search for jobs dynamically from a supported European job website.
    Filters are applied during the scrape or locally normalized.
    """
    try:
        scraper = get_scraper(source)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
        
    filters = SearchFilters(
        source=source,
        company=company, 
        keyword=keyword, 
        country=country, 
        city=city,
        remote=remote,
        salary_min=salary_min,
        employment_type=employment_type,
        page=page
    )
    
    try:
        jobs = await scraper.search(filters)
        return jobs
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scraper failed: {str(e)}")
    finally:
        await scraper.close()

@router.get("/jobs/{job_id}", response_model=JobSchema, summary="Get details for a specific job")
async def get_job_details(
    job_id: str = Path(..., description="The ID of the job"),
    source: str = Query(..., description="The ATS source"),
    company: str = Query(..., description="The company slug")
):
    """
    Fetch the detailed information for a specific job ID.
    Note: Some scrapers fetch all details in the list endpoint, others require this direct fetch.
    """
    try:
        scraper = get_scraper(source)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
        
    try:
        # In a real app without a DB, we would have to fetch the single job directly 
        # from the ATS if the API supports it, or fetch all and filter.
        # For simplicity, we just trigger search and filter.
        filters = SearchFilters(company=company)
        jobs = await scraper.search(filters)
        for job in jobs:
            if job.id == job_id:
                return job
        raise HTTPException(status_code=404, detail="Job not found on source")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scraper failed: {str(e)}")
    finally:
        await scraper.close()

@router.get("/sources", response_model=Dict[str, List[str]], summary="List supported sources")
async def get_sources():
    """Returns all ATS platforms currently supported by the scraper factory."""
    return {
        "supported_sources": [
            "greenhouse",
            "lever",
            "smartrecruiters",
            "personio",
            "ashby",
            "adzuna",
            "reed",
            "careerjet",
            "linkedin",
            "indeed",
            "glassdoor",
            "seek",
            "totaljobs",
            "cvlibrary",
            "stepstone"
        ]
    }

@router.get("/countries", response_model=List[str], summary="List supported countries")
async def get_countries():
    """Returns a static list of commonly targeted European countries for filtering."""
    return [
        "Germany", "United Kingdom", "France", "Netherlands", "Spain",
        "Italy", "Sweden", "Ireland", "Switzerland", "Austria"
    ]

@router.get("/states", response_model=List[str], summary="List supported states/regions")
async def get_states():
    """Returns a static list of regions."""
    return ["Berlin", "Bavaria", "Île-de-France", "Catalonia", "Lombardy"]

@router.get("/cities", response_model=List[str], summary="List supported cities")
async def get_cities():
    """Returns a static list of major European tech hubs."""
    return ["Berlin", "London", "Paris", "Amsterdam", "Madrid", "Munich", "Stockholm", "Dublin"]

@router.get("/companies", response_model=List[str], summary="List known companies")
async def get_companies():
    """
    Since this is a memory-only API without a DB, this returns a static list of 
    example European companies that use the supported ATS systems.
    """
    return ["contentful", "n26", "personio", "lever", "smartrecruiters"]

@router.get("/skills", response_model=List[str], summary="List available skills")
async def get_skills():
    """Returns a static list of skills for the keyword filter."""
    return ["Python", "FastAPI", "React", "TypeScript", "Rust", "Go", "Kubernetes", "AWS"]
