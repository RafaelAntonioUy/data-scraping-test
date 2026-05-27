import os
import re
import time
import pandas as pd
from bs4 import BeautifulSoup

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager

# =========================
# SETTINGS
# =========================

excel_path = "REVOL_v4.xlsx"  # Original file to read from AND append to
baseurl = "https://kitchenrestock.com"

total_pages = 113
save_interval = 5

# =========================
# HELPER FUNCTIONS
# =========================

def clean_text(value):
    """Normalize text for comparison"""
    if value is None or pd.isna(value):
        return ""
    
    value = str(value)
    if value.endswith(".0"):
        value = value[:-2]
        
    value = value.replace("\xa0", " ")
    value = value.strip()
    return value.lower()

def start_browser():
    """Starts standard Chrome browser for non-Cloudflare sites"""
    options = Options()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled")
    # options.add_argument("--headless") # Uncomment to run quietly in background
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    driver.set_page_load_timeout(30)
    return driver

# =========================
# LOAD EXCEL
# =========================

try:
    df = pd.read_excel(excel_path)
except FileNotFoundError:
    print(f"❌ Could not find {excel_path}! Make sure it is in the same folder as this script.")
    exit()

if "MFR" not in df.columns:
    print("❌ Critical Error: 'MFR' column not found in your spreadsheet!")
    exit()

# Create a clean memory set of all the MFRs you have already scraped
df["MFR_CLEAN"] = df["MFR"].apply(clean_text)
existing_mfrs = set(df["MFR_CLEAN"].dropna().unique())

print("✅ Excel Loaded:", len(df), "rows")
print(f"✅ Found {len(existing_mfrs)} previously scraped MFRs. Will skip these.")

# =========================
# SELENIUM SETUP
# =========================

driver = start_browser()
wait = WebDriverWait(driver, 8) 

# =========================
# PHASE 1: COLLECT PRODUCT LINKS
# =========================

productlinks = []

print(f"\n🚀 Starting link extraction for {total_pages} pages on Kitchen Restock...\n")

for page in range(1, total_pages + 1):
    if page == 1:
        url = f"{baseurl}/search?options%5Bprefix%5D=last&q=revol"
    else:
        url = f"{baseurl}/search?options%5Bprefix%5D=last&page={page}&q=revol"
        
    try:
        driver.get(url)
        time.sleep(3) 

        soup = BeautifulSoup(driver.page_source, "lxml")
        
        # Targeting the exact nested HTML structure provided
        selector = 'ul.grid li.js-pagination-result product-card div.card__media a'
        link_elements = soup.select(selector)
        
        if not link_elements:
            print(f"⚠️ No products found on page {page}. Skipping to next...")
            continue
            
        page_links_count = 0
        for a_tag in link_elements:
            href = a_tag.get("href")
            if href:
                full_link = baseurl + href if href.startswith("/") else href
                if full_link not in productlinks:
                    productlinks.append(full_link)
                    page_links_count += 1
                    
        print(f"📄 Page {page}/{total_pages} scanned | Found {page_links_count} new links")
                    
    except Exception as e:
        print(f"⚠️ Failed to load page {page}: {e}")

print("\n✅ TOTAL UNIQUE LINKS TO CHECK:", len(productlinks))

# =========================
# PHASE 2: SCRAPE PRODUCTS
# =========================

total_links_visited = 0
new_data_scraped = []
skipped_mfr_count = 0
discarded_links_count = 0

for link in productlinks:
    total_links_visited += 1
    print(f"\n==================================================")
    print(f"🌐 Link ({total_links_visited}/{len(productlinks)}): {link}")

    try:
        driver.get(link)
        
        # --- 1. FAST MFR CHECK ---
        mfr = None
        try:
            mfr_xpath = '//div[@class="specs-container"]//table//tbody//tr[th[contains(text(), "Manufacturer Part")]]/td'
            mfr_element = wait.until(EC.presence_of_element_located((By.XPATH, mfr_xpath)))
            mfr = mfr_element.get_attribute("textContent").strip()
                
        except TimeoutException:
            print("❌ MFR element not found in specs table → Discarding Invalid Link")
            discarded_links_count += 1
            continue

        mfr_clean = clean_text(mfr)
        
        # --- 2. THE SKIP LOGIC ---
        if mfr_clean in existing_mfrs:
            print(f"⏭️ MATCH FOUND IN EXCEL ('{mfr_clean}') → Already scraped! Discarding & Skipping...")
            skipped_mfr_count += 1
            continue
            
        print(f"⏳ NEW PRODUCT DETECTED ('{mfr_clean}') → Scraping remaining details...")

        # --- 3. SCRAPE THE REST OF THE DATA ---
        
        # TITLE 
        try:
            title_xpath = '//h1'
            title_element = wait.until(EC.presence_of_element_located((By.XPATH, title_xpath)))
            raw_title = title_element.get_attribute("textContent").strip()
        except TimeoutException:
            raw_title = "N/A"

        # IMAGE URL
        try:
            img_xpath = '//div[contains(@class, "pmslider-slide--inner")]//img'
            img_element = wait.until(EC.presence_of_element_located((By.XPATH, img_xpath)))
            src = img_element.get_attribute("src")
            
            if src:
                if src.startswith("//"):
                    image_url = "https:" + src
                else:
                    image_url = src
            else:
                image_url = "N/A"
        except TimeoutException:
            image_url = "N/A"

        # =====================
        # TERMINAL OUTPUT
        # =====================
        print("\n[ NEW SCRAPED DATA ]")
        print(f"MFR:        {mfr}")
        print(f"Title:      {raw_title}")
        print(f"Image URL:  {image_url}")
        print("-" * 50)

        # =====================
        # PREPARE NEW ROW
        # =====================
        new_row = {
            "Item No.": "N/A",
            "MFR": mfr,
            "Group Name": "REVOL",
            "Item Description": raw_title,
            "Image URL": image_url,
            "Overview": "N/A",
            "Length": "N/A",
            "Width": "N/A",
            "Height": "N/A",
            "Shape": "N/A",
            "Material": "N/A",
            "Features": "N/A",
            "Volume": "N/A",
            "Capacity": "N/A",
            "Edge Style": "N/A",
            "EAN Code": "N/A",
            "Pattern": "N/A",
            "Barcode": "N/A",
            "Product Link": link
        }
        
        new_data_scraped.append(new_row)
        existing_mfrs.add(mfr_clean)

    # =====================
    # FATAL ERROR RECOVERY
    # =====================
    except Exception as e:
        print(f"\n⚠️ FATAL BROWSER ERROR on {link}")
        print(f"Error Details: {e}")
        print("🔄 Restarting the browser to clear memory and continue...")
        
        try:
            driver.quit() 
        except:
            pass
            
        driver = start_browser()
        wait = WebDriverWait(driver, 8)

    # =====================
    # SAVE NEW DATA BATCHES
    # =====================
    if len(new_data_scraped) > 0 and len(new_data_scraped) % save_interval == 0:
        new_df = pd.DataFrame(new_data_scraped)
        combined_df = pd.concat([df, new_df], ignore_index=True)
        combined_df.drop(columns=["MFR_CLEAN"], errors='ignore').to_excel(excel_path, index=False)
        print(f"💾 Progress saved to {excel_path} (Added {len(new_data_scraped)} new items)")

# =========================
# FINAL SAVE & STATISTICS
# =========================

if len(new_data_scraped) > 0:
    new_df = pd.DataFrame(new_data_scraped)
    combined_df = pd.concat([df, new_df], ignore_index=True)
    combined_df.drop(columns=["MFR_CLEAN"], errors='ignore').to_excel(excel_path, index=False)

print("\n==================================================")
print("🎉 SCRAPING COMPLETE - FINAL STATISTICS")
print("==================================================")
print(f"Total links visited/checked:            {total_links_visited}")
print(f"Links discarded (No MFR found):         {discarded_links_count}")
print(f"Links discarded (Already in Spreadsheet):{skipped_mfr_count}")
print(f"Brand new products actively appended:   {len(new_data_scraped)}")
print(f"Final data saved to:                    {excel_path}")
print("==================================================")

try:
    driver.quit()
except OSError:
    pass # Silently ignores the Windows handle cleanup bug from previous runs if any persist