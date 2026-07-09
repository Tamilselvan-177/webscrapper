import asyncio
import sys
from app.core.browser_client import BrowserClient
from bs4 import BeautifulSoup

async def run_playwright_test(executable_path=None):
    if executable_path:
        print(f"Initializing Playwright with custom engine: {executable_path}")
    else:
        print("Initializing Playwright with standard Chromium engine...")
        
    client = BrowserClient(executable_path=executable_path)
    
    try:
        page = await client.get_page()
        
        # Testing on a well-known site that requires JS to fully render content
        test_url = "https://news.ycombinator.com/jobs"
        print(f"Navigating to {test_url} ...")
        
        await page.goto(test_url, wait_until="domcontentloaded")
        
        title = await page.title()
        print(f"\n✅ Success! Page Title: '{title}'")
        
        content = await page.content()
        soup = BeautifulSoup(content, "html.parser")
        
        # Look for job listings on HN
        job_links = soup.find_all("tr", class_="athing")
        print(f"✅ Successfully read DOM. Found {len(job_links)} jobs rendered on the page.")
        
        if job_links:
            first_job = job_links[0].get_text(strip=True)
            print(f"✅ Sample Output: {first_job[:80]}...\n")

    except Exception as e:
        print(f"\n❌ Browser test failed: {e}")
    finally:
        print("Closing browser...")
        await client.close()

if __name__ == "__main__":
    # If a command line argument is passed, use it as the executable_path
    path = sys.argv[1] if len(sys.argv) > 1 else None
    asyncio.run(run_playwright_test(path))
