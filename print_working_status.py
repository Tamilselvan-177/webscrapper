import asyncio
from app.scrapers.factory import get_scraper
from app.models.filters import SearchFilters
import logging

logging.basicConfig(level=logging.ERROR)

async def test_all_sources():
    # List of all source keys to test with appropriate test queries
    sources = [
        ("greenhouse", "developer", "London", "openai"),
        ("lever", "developer", "London", "netflix"),
        ("smartrecruiters", "developer", "London", "ubisoft"),
        ("personio", "developer", "London", "personio"),
        ("ashby", "developer", "London", "openai"),
        ("linkedin", "developer", "London", None),
        ("adzuna", "developer", "London", None),
        ("reed", "developer", "London", None),
        ("indeed", "developer", "London", None),
        ("seek", "engineer", "Sydney", None),
        ("totaljobs", "developer", "London", None),
        ("cvlibrary", "developer", "London", None),
        ("careerjet", "developer", "London", None),
        ("stepstone", "developer", "London", None),
        ("glassdoor", "developer", "London", None),
        ("jobbank", "developer", "Toronto", None),
        ("talentcom", "developer", "London", None),
        ("randstad", "developer", "London", None),
        ("michaelpage", "consultant", "London", None),
        ("hays", "accountant", "London", None),
        ("xing", "entwickler", "Berlin", None),
        ("jobrapido", "developer", "Manchester", None),
        ("irishjobs", "developer", "Dublin", None),
        ("jobsireland", "engineer", "Cork", None),
        ("eures", "software", "Amsterdam", None),
        ("workopolis", "engineer", "Toronto", None),
        ("jora", "developer", "Sydney", None),
        ("monster", "developer", "New York", None),
        ("careerone", "developer", "Brisbane", None),
        ("eluta", "analyst", "Toronto", None),
        ("workforceaustralia", "manager", "Melbourne", None),
    ]

    print("=" * 75)
    print("WAYMAX GLOBAL - ALL SUPPORTED JOB PORTALS WORKING STATUS")
    print("=" * 75)
    
    working_count = 0
    for s_name, kw, loc, comp in sources:
        try:
            s = get_scraper(s_name)
            filters = SearchFilters(source=s_name, keyword=kw, city=loc, company=comp)
            jobs = await s.search(filters)
            count = len(jobs)
            if count > 0:
                working_count += 1
                status = "✅ WORKING"
                sample = jobs[0].title[:35]
            else:
                status = "⚠️ 0 JOBS"
                sample = "N/A"
            print(f"{s_name.ljust(20)} | {status.ljust(12)} | {str(count).rjust(3)} jobs | {sample}")
        except Exception as e:
            print(f"{s_name.ljust(20)} | ❌ ERROR     |   0 jobs | {str(e)[:35]}")
            
    print("=" * 75)
    print(f"TOTAL WORKING PORTALS: {working_count} / {len(sources)}")
    print("=" * 75)

if __name__ == "__main__":
    asyncio.run(test_all_sources())
