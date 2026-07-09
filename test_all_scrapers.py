import asyncio
import json
from app.scrapers.factory import get_scraper
from app.models.filters import SearchFilters
from app.models.job import JobSchema

async def run_tests():
    sources = [
        ("greenhouse", "contentful"),
        ("lever", "lever"),
        ("smartrecruiters", "smartrecruiters"),
        ("personio", "personio"),
        ("ashby", "ashby")
    ]
    
    for source_name, company in sources:
        print(f"\n--- Testing {source_name.upper()} ---")
        try:
            scraper = get_scraper(source_name)
            filters = SearchFilters(company=company)
            # Fetch a few jobs to test validation
            jobs = await scraper.search(filters)
            print(f"[{source_name}] Successfully fetched and validated {len(jobs)} jobs.")
            
            if jobs:
                print(f"[{source_name}] Sample Job: {jobs[0].title} - {jobs[0].job_url}")
            else:
                print(f"[{source_name}] No jobs found for {company} or empty state handled correctly.")
                
            await scraper.close()
        except Exception as e:
            print(f"[{source_name}] Test failed: {e}")

if __name__ == "__main__":
    asyncio.run(run_tests())
