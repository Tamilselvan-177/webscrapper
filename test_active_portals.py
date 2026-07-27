import sys
import time
import asyncio
import traceback
from app.scrapers.factory import get_scraper
from app.scrapers.base import SearchFilters

# Set utf-8 encoding if possible, or avoid emojis
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Active Portals in ResumeBuddy to test
PORTALS_TO_TEST = [
    # Global / Major Portals
    ("linkedin", "developer", "London"),
    ("adzuna", "developer", "London"),
    ("jobrapido", "developer", "London"),
    
    # UK & European Portals
    ("reed", "engineer", "London"),
    ("glassdoor", "developer", "London"),
    ("eures", "developer", "Berlin"),
    
    # Irish Portals
    ("irishjobs", "engineer", "Dublin"),
    ("jobsireland", "engineer", "Dublin"),
    
    # Australia & Canada
    ("seek", "engineer", "Sydney"),
    ("jora", "engineer", "Sydney"),
    
    # Recruitment Agencies
    ("randstad", "developer", "London"),
    ("michaelpage", "developer", "London"),
    ("hays", "developer", "London"),
    
    # ATS Systems
    ("lever", "engineer", "London"),
    ("ashby", "engineer", "London"),
    ("greenhouse", "engineer", "London"),
    ("smartrecruiters", "engineer", "London"),
    ("personio", "engineer", "London"),
]

async def test_portal(source, keyword, city):
    print(f"\n--- Testing [{source.upper()}] (Keyword: '{keyword}', City: '{city}') ---", flush=True)
    start_time = time.time()
    try:
        scraper = get_scraper(source)
        filters = SearchFilters(source=source, keyword=keyword, city=city, remote=False)
        
        # Try full search (with description normalization) up to 25 seconds
        try:
            jobs = await asyncio.wait_for(scraper.search(filters), timeout=25.0)
            job_list = jobs.jobs if hasattr(jobs, "jobs") else jobs
        except asyncio.TimeoutError:
            print("   [i] Full description normalization took >25s, checking raw job feed...", flush=True)
            job_list = await asyncio.wait_for(scraper.get_jobs(filters), timeout=20.0)
            
        duration = round(time.time() - start_time, 2)
        count = len(job_list) if job_list else 0
        
        if count > 0:
            sample = job_list[0]
            title = sample.title if hasattr(sample, "title") else sample.get("title", "N/A")
            company = sample.company if hasattr(sample, "company") else sample.get("company", "N/A")
            url = sample.job_url if hasattr(sample, "job_url") else sample.get("job_url", "N/A")
            
            print(f"[SUCCESS] Found {count} jobs in {duration}s!")
            print(f"   Sample Job : {title} @ {company}")
            print(f"   Sample URL : {url[:80]}...")
            return (source, "WORKING [OK]", count, duration, f"{title} ({url[:40]}...)")
        else:
            print(f"[0 JOBS] Found in {duration}s (Check keyword/location or rate limit)")
            return (source, "0 JOBS [WARN]", 0, duration, "No jobs matched keyword")
            
    except Exception as e:
        duration = round(time.time() - start_time, 2)
        err_msg = str(e).split("\n")[0]
        print(f"[ERROR/BLOCKED] in {duration}s: {err_msg}")
        return (source, "ERROR [FAIL]", 0, duration, err_msg[:50])

async def run_tests():
    print("=" * 70)
    print("[*] TESTING ACTIVE RESUMEBUDDY JOB PORTALS")
    print("=" * 70)
    
    results = []
    for source, keyword, city in PORTALS_TO_TEST:
        res = await test_portal(source, keyword, city)
        results.append(res)
            
    print("\n" + "=" * 80)
    print("FINAL SUMMARY REPORT OF ACTIVE RESUMEBUDDY PORTALS")
    print("=" * 80)
    print(f"{'Portal':<16} | {'Status':<12} | {'Jobs':<6} | {'Time':<6} | {'Sample / Note'}")
    print("-" * 80)
    
    working_count = 0
    for source, status, count, duration, note in results:
        print(f"{source.upper():<16} | {status:<12} | {count:<6} | {duration:<5}s | {note}")
        if "WORKING" in status or "0 JOBS" in status:
            working_count += 1
            
    print("-" * 80)
    print(f"Total Tested: {len(results)} | Total Functional: {working_count}/{len(results)}")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(run_tests())
