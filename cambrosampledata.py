import time
import re
import random
import os
import pandas as pd
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from bs4 import BeautifulSoup, soup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Selenium imports
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# -----------------------------
# Selenium Setup (only for collecting product links)
# -----------------------------
chrome_options = Options()
chrome_options.add_argument("--headless=new")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--disable-extensions")
chrome_options.add_argument("--disable-blink-features=AutomationControlled")
chrome_options.add_argument("--window-size=1920,1080")
chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64)")

# Disable images to speed up page load
prefs = {"profile.managed_default_content_settings.images": 2}
chrome_options.add_experimental_option("prefs", prefs)

service = Service(
    "C:/Users/sapadmin/Downloads/chromedriver-win64/chromedriver-win64/chromedriver.exe"
)
driver = webdriver.Chrome(service=service, options=chrome_options)
driver.set_page_load_timeout(60)
wait = WebDriverWait(driver, 20)

def safe_get(url, retries=3):
    for attempt in range(retries):
        try:
            driver.get(url)
            wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            return True
        except Exception as e:
            print(f"⚠️ Selenium timeout on {url} (attempt {attempt+1}) -> {e}")
            if attempt < retries - 1:
                time.sleep(2 + attempt)
            else:
                print("❌ Skipping this URL (Selenium).")
                return False
    return False

# -----------------------------
# Category URLs
# -----------------------------
urls = [
    "https://shop.mohd.it/en/brands/broggi.html"
]

# -----------------------------
# Collect product links
# -----------------------------
all_product_links = []

for url in urls:
    print(f"🔎 Collecting product links from: {url}")
    if not safe_get(url):
        continue

    try:
        products = driver.find_elements(By.CSS_SELECTOR, 'a.product-item-link')
        links = [p.get_attribute("href") for p in products if p.get_attribute("href")]
        print(f"  → Found {len(links)} product links")
        all_product_links.extend(links)
        time.sleep(random.uniform(0.8, 1.8))
    except Exception as e:
        print(f"⚠️ Error extracting product links: {e}")

all_product_links = list(dict.fromkeys(all_product_links))
print(f"✅ Total unique product links collected: {len(all_product_links)}")

driver.quit()

# -----------------------------
# Requests session with retries
# -----------------------------
session = requests.Session()
retries = Retry(
    total=3,
    backoff_factor=0.6,
    status_forcelist=[429, 500, 502, 503, 504],
    raise_on_status=False
)
adapter = HTTPAdapter(max_retries=retries, pool_connections=100, pool_maxsize=100)
session.mount("http://", adapter)
session.mount("https://", adapter)

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# -----------------------------
# Product page parser
# -----------------------------
def parse_product_page(url, session, timeout=20):
    
    out = {
        "brand": "BROGGI",
    "product_name": "",
    "manufacturer_id": mfr_code,
    "product_url": url,
    "image_url": "",
    "availability": "N/A",
    "category": "N/A",
    "product_description_overview": "",
    "scraped_at": datetime.now().strftime("%Y-%m-%d"),
    "product_specs": ""
    }

    try:
        resp = session.get(url, headers=DEFAULT_HEADERS, timeout=timeout)
        if resp.status_code >= 400:
            out["Item Name"] = f"HTTP {resp.status_code}"
            return out

        soup = BeautifulSoup(resp.text, "lxml")
        page_text = soup.get_text()

        if mfr_code not in page_text:
            return None  # skip product that doesn't match MFR code


        from datetime import datetime

# -----------------------------
# BROGGI parsing inside parse_product_page
# -----------------------------

# Product name
        h1 = soup.find("h1")
        out["product_name"] = h1.get_text(strip=True) if h1 else "N/A"

# Product image
        img = soup.find("img")
        out["image_url"] = img["src"] if img else "N/A"

# Product description/overview
        desc = soup.find("div", class_="product-description")
        out["product_description_overview"] = desc.get_text(strip=True) if desc else "N/A"

# Product specs
        specs = soup.find("table")
        out["product_specs"] = specs.get_text(" | ", strip=True) if specs else "N/A"

# Scraped date
        out["scraped_at"] = datetime.now().strftime("%Y-%m-%d")


        specs_title = soup.select_one("p.specs-text")
        out["Specs Title"] = specs_title.get_text(strip=True) if specs_title else ""

        specs = {}
        dts = soup.select("dl#tbSpecSheetRows dt")
        dds = soup.select("dl#tbSpecSheetRows dd")
        if len(dts) == len(dds):
            for dt, dd in zip(dts, dds):
                specs[dt.get_text(strip=True)] = dd.get_text(strip=True)

        out.update(specs)

        html = resp.text
        if "Overall Dimensions:" in html:
            m = re.search(r"Overall Dimensions:?\s*(.*?)</p>", html, re.DOTALL)
            if m:
                out["Overall Dimensions"] = re.sub(r"<.*?>", "", m.group(1)).strip()

        return out

    except Exception as e:
        return {"Item Name": f"ERROR: {e}", "Link": url}

# -----------------------------
# Parallel fetch
# -----------------------------
results = []
errors = []

print("🚀 Starting product scraping...")
start = time.time()

with ThreadPoolExecutor(max_workers=20) as executor:
    futures = {executor.submit(parse_product_page, u, session): u for u in all_product_links}
    for i, future in enumerate(as_completed(futures), 1):
        try:
            results.append(future.result())
        except Exception:
            errors.append(futures[future])
        if i % 25 == 0 or i == len(futures):
            print(f"  Progress: {i}/{len(futures)} | {time.time()-start:.1f}s")

# -----------------------------
# Save to Excel (RENAMED)
# -----------------------------
if results:
    df = pd.DataFrame(results)

    core_cols = [
        "Item Name", "Item #", "MFR #", "Image URL",
        "Overview", "Specs Title", "Overall Dimensions", "Link"
    ]
    df = df[[c for c in core_cols if c in df.columns] +
            [c for c in df.columns if c not in core_cols]]

    output_file = "CAMBRO SAMPLE DATA.xlsx"

    try:
        if os.path.exists(output_file):
            os.remove(output_file)
        df.to_excel(output_file, index=False, engine="openpyxl")
        print(f"✅ Saved {len(df)} rows to {output_file}")
    except PermissionError:
        print(f"❌ CLOSE Excel file first: {output_file}")

else:
    print("⚠️ No data saved")

print("🎯 DONE")
