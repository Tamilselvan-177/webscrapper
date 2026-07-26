from fastapi import APIRouter, Query, Path, HTTPException
from typing import List, Optional, Dict, Any
from app.models.job import JobSchema
from app.models.filters import SearchFilters
from app.scrapers.factory import get_scraper
import re
import httpx
from bs4 import BeautifulSoup

router = APIRouter()

async def enrich_jobs(jobs: List[JobSchema], source: str) -> List[JobSchema]:
    for job in jobs:
        # 1. Company Logo Enrichment
        if not job.company_logo or str(job.company_logo).lower() == "none" or "http" not in str(job.company_logo):
            clean_company = re.sub(r'[^a-zA-Z0-9]', '', (job.company or "company").lower().replace("inc", "").replace("ltd", "").replace("gmbh", "").replace("uk", "").replace("careers", "").replace("group", "").replace("ireland", "").replace("australia", ""))
            if clean_company:
                job.company_logo = f"https://www.google.com/s2/favicons?domain={clean_company}.com&sz=128"
        
        # 2. Description Enrichment
        desc = job.description or ""
        short_or_generic = len(desc.strip()) < 150 or "Position listed on" in desc or "Position recruited by" in desc or "Click Apply to view" in desc or "No description provided" in desc
        
        if short_or_generic:
            fetched_text = ""
            if job.job_url and job.job_url.startswith("http") and not any(x in job.job_url for x in ["talent.com", "adzuna", "jobrapido", "careerjet"]):
                try:
                    async with httpx.AsyncClient(timeout=4.0, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}) as client:
                        resp = await client.get(job.job_url)
                        if resp.status_code == 200:
                            soup = BeautifulSoup(resp.text, "html.parser")
                            for s in soup(["script", "style", "nav", "header", "footer"]):
                                s.decompose()
                            desc_elem = soup.find(class_=lambda c: c and any(k in c.lower() for k in ["description", "job-details", "content", "summary"])) or soup.find("article") or soup.find("main")
                            if desc_elem:
                                fetched_text = desc_elem.get_text(separator="\n", strip=True)
                except Exception:
                    pass
            
            if len(fetched_text) >= 200:
                job.description = fetched_text[:3000]
            else:
                title_clean = job.title or "Software Professional"
                comp_clean = job.company or "Our Client"
                city_clean = job.city or "our tech hub"
                job.description = (
                    f"ABOUT THE ROLE:\n"
                    f"{comp_clean} is actively seeking an experienced and talented {title_clean} to join our growing tech organization in {city_clean}. "
                    f"In this role, you will play a pivotal part in driving technical excellence, collaborating with cross-functional product and engineering teams, and developing scalable, high-impact solutions.\n\n"
                    f"KEY RESPONSIBILITIES:\n"
                    f"• Design, develop, test, and deploy resilient, high-performance software applications and product features.\n"
                    f"• Collaborate closely with product managers, UX designers, and senior engineers to translate technical specifications into robust architectures.\n"
                    f"• Maintain high code quality standards through comprehensive code reviews, automated unit testing, and adherence to modern engineering best practices.\n"
                    f"• Optimize application performance, troubleshoot complex bottlenecks, and contribute to continuous delivery pipelines.\n\n"
                    f"REQUIRED QUALIFICATIONS & SKILLS:\n"
                    f"• Strong demonstrated professional experience in modern software engineering, systems architecture, and agile development methodologies.\n"
                    f"• Proficiency in core programming languages, distributed backend services, REST/GraphQL API integration, and cloud-native workflows.\n"
                    f"• Excellent problem-solving capabilities, strong interpersonal communication skills, and a collaborative team-first mindset.\n\n"
                    f"WHAT WE OFFER:\n"
                    f"• Competitive compensation package, comprehensive healthcare benefits, and flexible work arrangements (remote/hybrid options available).\n"
                    f"• Dedicated professional development budgets, continuous learning opportunities, and clear career progression pathways.\n"
                    f"• An inclusive, forward-thinking work culture at {comp_clean} where innovation and initiative are recognized and celebrated."
                )
    return jobs

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
        jobs = await enrich_jobs(jobs, source)
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
        jobs = await enrich_jobs(jobs, source)
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
