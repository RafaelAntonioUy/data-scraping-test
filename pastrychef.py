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
baseurl = "https://www.pastrychefsboutique.com"

total_pages = 94
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
    """Helper function to start/restart the browser to prevent memory leaks"""
    options = Options()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled")
    # options.add_argument("--headless")
    
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
wait = WebDriverWait(driver, 5)

# =========================
# COLLECT PRODUCT LINKS
# =========================

productlinks = []

for page in range(1, total_pages + 1):
    url = f"{baseurl}/module/ambjolisearch/jolisearch?s=revol&page={page}"
    print(f"\n🔎 Scraping search page {page}/{total_pages}")

    try:
        driver.get(url)
        time.sleep(4) 

        soup = BeautifulSoup(driver.page_source, "lxml")
        
        # Look for the links inside the thumbnail-top div
        products = soup.select('div.thumbnail-top a')

        for item in products:
            href = item.get("href")
            if href:
                # Handle absolute vs relative URLs
                full_link = href if href.startswith("http") else baseurl + href
                if full_link not in productlinks:
                    productlinks.append(full_link)
                    
    except Exception as e:
        print(f"⚠️ Failed to load page {page}: {e}")

print("\n✅ TOTAL UNIQUE LINKS TO CHECK:", len(productlinks))

# =========================
# SCRAPE PRODUCTS
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
        try:
            mfr_xpath = '//div[@class="product-reference"]//span'
            mfr_element = wait.until(EC.presence_of_element_located((By.XPATH, mfr_xpath)))
            mfr = mfr_element.get_attribute("textContent").strip()
            
        except TimeoutException:
            print("❌ No MFR found on page → Discarding Invalid Link")
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
        
        # IMAGE URL
        try:
            img_xpath = '//div[@class="product-cover"]//img'
            img_element = wait.until(EC.presence_of_element_located((By.XPATH, img_xpath)))
            image_url = img_element.get_attribute("src")
        except TimeoutException:
            image_url = "N/A"
            
        # TITLE (Added as a bonus to fill 'Item Description')
        try:
            title_xpath = '//h1[@itemprop="name"]'
            title_element = wait.until(EC.presence_of_element_located((By.XPATH, title_xpath)))
            raw_title = title_element.get_attribute("textContent").strip()
        except TimeoutException:
            raw_title = "N/A"

        # OVERVIEW / DESCRIPTION
        try:
            desc_xpath = '//div[@itemprop="description"]'
            desc_element = wait.until(EC.presence_of_element_located((By.XPATH, desc_xpath)))
            overview = desc_element.get_attribute("textContent").strip()
            overview = re.sub(r'\n+', '\n', overview) # Clean up spacing
        except TimeoutException:
            overview = "N/A"

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
            "Overview": overview,
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
        existing_mfrs.add(mfr_clean) # Add to memory to prevent duplicates in the same run

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
        wait = WebDriverWait(driver, 5)

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
print(f"Links discarded (Invalid layout/No MFR):{discarded_links_count}")
print(f"Links discarded (Already in spreadsheet):{skipped_mfr_count}")
print(f"Brand new products actively appended:   {len(new_data_scraped)}")
print(f"Final data saved to:                    {excel_path}")
print("==================================================")

driver.quit()