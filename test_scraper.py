import asyncio
import json
from app.scrapers.greenhouse import GreenhouseScraper
from app.models.filters import SearchFilters

async def test_greenhouse():
    scraper = GreenhouseScraper()
    filters = SearchFilters(source="greenhouse", company="contentful")
    print(f"Searching Greenhouse at {filters.company}...")
    
    try:
        jobs = await scraper.search(filters)
        print(f"Found {len(jobs)} jobs.")
        if jobs:
            print("\nSample Job JSON Output:")
            print(jobs[0].model_dump_json(indent=2))
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await scraper.close()

if __name__ == "__main__":
    asyncio.run(test_greenhouse())
