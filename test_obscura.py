import asyncio
import sys
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

async def run_obscura_test(ws_endpoint: str):
    print(f"Connecting to Obscura over CDP: {ws_endpoint}")
    
    playwright = await async_playwright().start()
    
    try:
        # Connect to the already running Obscura engine
        browser = await playwright.chromium.connect_over_cdp(ws_endpoint)
        
        # Obscura might already have default contexts, but we can create a new page
        context = browser.contexts[0] if browser.contexts else await browser.new_context()
        page = await context.new_page()
        
        test_url = "https://news.ycombinator.com/jobs"
        print(f"Navigating to {test_url} ...")
        
        await page.goto(test_url, wait_until="domcontentloaded")
        
        title = await page.title()
        print(f"\nSuccess! Page Title: '{title}'")
        
        content = await page.content()
        soup = BeautifulSoup(content, "html.parser")
        
        job_links = soup.find_all("tr", class_="athing")
        print(f"Successfully read DOM. Found {len(job_links)} jobs rendered on the page.")
        
        if job_links:
            first_job = job_links[0].get_text(strip=True)
            print(f"Sample Output: {first_job[:80]}...\n")

    except Exception as e:
        print(f"\nObscura test failed: {e}")
    finally:
        print("Closing connection...")
        if 'browser' in locals():
            await browser.close()
        await playwright.stop()

if __name__ == "__main__":
    endpoint = sys.argv[1] if len(sys.argv) > 1 else "ws://127.0.0.1:9222/devtools/browser"
    asyncio.run(run_obscura_test(endpoint))
