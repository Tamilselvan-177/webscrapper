import asyncio
from app.scrapers.factory import get_scraper
from app.models.filters import SearchFilters
import logging

logging.basicConfig(level=logging.WARNING)

async def test_all():
    portals = [
        ('randstad', 'developer', 'London'),
        ('michaelpage', 'consultant', 'London'),
        ('hays', 'accountant', 'London'),
        ('xing', 'entwickler', 'Berlin'),
        ('jobrapido', 'developer', 'Manchester'),
        ('irishjobs', 'developer', 'Dublin'),
        ('jobsireland', 'engineer', 'Cork'),
        ('eures', 'software', 'Amsterdam')
    ]
    print("=" * 60)
    print("TESTING ALL 8 NEWLY IMPLEMENTED SCRAPERS VIA FACTORY")
    print("=" * 60)
    for s_name, kw, loc in portals:
        try:
            s = get_scraper(s_name)
            jobs = await s.search(SearchFilters(source=s_name, keyword=kw, city=loc))
            sample = jobs[0].title if jobs else "None"
            print(f"{s_name.ljust(15)} -> Found {str(len(jobs)).rjust(3)} jobs | Sample: {sample[:40]}")
        except Exception as e:
            print(f"{s_name.ljust(15)} -> ERROR: {e}")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(test_all())
