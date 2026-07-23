import asyncio
import json
from app.scrapers.factory import get_scraper
from app.models.filters import SearchFilters
from app.models.job import JobSchema

async def run_tests():
    sources = [
        ("greenhouse", "contentful", None, None),
        ("lever", "figma", None, None),
        ("smartrecruiters", "ikea", None, None),
        ("personio", "personio", None, None),
        ("ashby", "notion", None, None),
        ("adzuna", None, "developer", "London"),
        ("reed", None, "engineer", "London"),
        ("careerjet", None, "developer", "London"),
        ("linkedin", None, "developer", "London"),
        ("indeed", None, "developer", "London"),
        ("glassdoor", None, "developer", "London"),
        ("seek", None, "engineer", "Sydney"),
        ("totaljobs", None, "developer", "London"),
        ("cvlibrary", None, "developer", "London"),
        ("stepstone", None, "developer", "London"),
    ]
    
    working = 0
    empty = 0

    for source_name, company, keyword, city in sources:
        print(f"\n--- Testing {source_name.upper()} ---")
        try:
            scraper = get_scraper(source_name)
            filters = SearchFilters(source=source_name, company=company, keyword=keyword, city=city)
            # Fetch a few jobs to test validation
            jobs = await scraper.search(filters)
            print(f"[{source_name}] Successfully fetched and validated {len(jobs)} jobs.")
            
            if jobs:
                working += 1
                print(f"[{source_name}] Sample Job: {jobs[0].title} - {jobs[0].job_url}")
            else:
                empty += 1
                print(f"[{source_name}] No jobs found for {company} or empty state handled correctly.")
                
            await scraper.close()
        except Exception as e:
            print(f"[{source_name}] Test failed: {e}")

    print(f"\nSummary: {working} sources returned jobs, {empty} sources returned empty results.")

if __name__ == "__main__":
    asyncio.run(run_tests())
