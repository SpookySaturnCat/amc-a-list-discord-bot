import asyncio
from urllib.request import Request, urlopen
from bs4 import BeautifulSoup

def _sync_fetch():
    """Synchronous HTTP fetch targeting AMC's public sitemap XML."""
    url = "https://www.amctheatres.com/sitemaps/sitemap-theatres.xml"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    req = Request(url, headers=headers)

    # Execute request using standard system socket bindings
    with urlopen(req, timeout=10) as response:
        return response.read().decode('utf-8')

async def fetch_sample_data():
    """Asynchronous wrapper to prevent blocking the Discord event loop."""
    loop = asyncio.get_running_loop()
    try:
        # Offload network request to a background thread
        xml_data = await loop.run_in_executor(None, _sync_fetch)

        # Parse XML payload using BeautifulSoup
        soup = BeautifulSoup(xml_data, "xml")
        urls = soup.find_all("loc")

        if urls:
            first_theater = urls[0].text
            total_locations = len(urls)
            return f"Successfully fetched AMC Sitemap!\n**Total Theaters Found:** {total_locations}\n**Sample Entry:** `{first_theater}`"
        else:
            return "Fetched page successfully, but no URL tags were found."

    except Exception as e:
        return f"Scraping error: {e}"

# Test script standalone execution
if __name__ == "__main__":
    result = asyncio.run(fetch_sample_data())
    print(result)