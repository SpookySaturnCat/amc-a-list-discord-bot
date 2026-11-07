import asyncio
import json
import os
from playwright.async_api import async_playwright

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
BROWSER_PROFILE_DIR = os.path.join(DATA_DIR, "browser_profile")


# Test execution for Persistent Playwright Profile Scraper
async def test_persistent_scrape():
    url = "https://www.amctheatres.com/movie-theatres/savannah/amc-classic-savannah-11/showtimes/today"
    os.makedirs(BROWSER_PROFILE_DIR, exist_ok=True)

    async with async_playwright() as p:
        print("Launching Persistent Chromium Session...")
        context = await p.chromium.launch_persistent_context(
            user_data_dir=BROWSER_PROFILE_DIR,
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-infobars",
                "--window-size=1920,1080",
            ],
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
            locale="en-US",
            timezone_id="America/New_York"
        )

        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)

        page = context.pages[0] if context.pages else await context.new_page()

        try:
            print(f"Navigating to {url}...")
            response = await page.goto(url, wait_until="domcontentloaded", timeout=25000)
            print(f"Page Status: {response.status}")

            await page.wait_for_selector("script#__NEXT_DATA__", timeout=12000)
            script_handle = await page.query_selector("script#__NEXT_DATA__")

            if script_handle:
                raw_json = await script_handle.inner_text()
                data = json.loads(raw_json)

                props = data.get("props", {}).get("pageProps", {})
                groupings = props.get("showtimes", {}).get("filmGroupings", [])

                print(f"\n--- SUCCESS: Extracted {len(groupings)} Movies ---")
                for group in groupings[:3]:
                    film = group.get("film", {})
                    title = film.get("sortableTitle") or film.get("title")
                    media = film.get("media", {})
                    poster = media.get("poster2x") or media.get("poster1x") or ""
                    times = [st.get("displayShowtime") or st.get("showDateTimeLocal") for st in group.get("showtimes", [])]
                    print(f"Title: {title}")
                    print(f"Poster: {poster}")
                    print(f"Times: {times[:4]}")
                    print("-" * 30)
            else:
                print("Failed to find __NEXT_DATA__ script tag.")

        except Exception as e:
            print(f"Persistent Scraping Error: {e}")
        finally:
            await context.close()


if __name__ == "__main__":
    asyncio.run(test_persistent_scrape())