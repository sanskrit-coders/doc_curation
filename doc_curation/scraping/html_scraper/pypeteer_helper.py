import asyncio
import time
from pyppeteer import launch
from bs4 import BeautifulSoup

async def init_browser():
  browser = await launch(headless=True)
  page = await browser.newPage()

  # Track network requests with a counter
  request_counter = {"count": 0}
  def log_request(req):
    request_counter["count"] += 1
    print(f"Request #{request_counter['count']}: {req.url}")

  page.on('request', log_request)

  return browser, page

async def fetch_soup(page, url: str, wait_until: str = 'networkidle0') -> BeautifulSoup:
  """
  Fetch a page using an existing Pyppeteer page object.
  Wait until network is idle, then pause 2s, return BeautifulSoup.
  """
  start = time.perf_counter()
  await page.goto(url, waitUntil=wait_until, timeout=60000)

  # Ensure idle for 2 seconds
  await asyncio.sleep(2)

  html = await page.content()
  end = time.perf_counter()
  print(f"Time taken for {url}: {end - start:.2f} seconds")

  return BeautifulSoup(html, 'html.parser')

async def main():
  browser, page = await init_browser()

  urls = [
    "https://www.ebharatisampat.in/readbook3.php?bookid=ODk4MDAxMDY5OTI2OTY4&pageno=MjI0MjQyNjk5NTk=",
    # add more URLs here
  ]

  for url in urls:
    soup = await fetch_soup(page, url)
    print("Page title:", soup.title.string if soup.title else "No title")

  await browser.close()

if __name__ == "__main__":
  asyncio.get_event_loop().run_until_complete(main())
