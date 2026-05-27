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
baseurl = "https://home.hospitalityprovisions.com"
search_url = "https://home.hospitalityprovisions.com/pages/rapid-search-results?q=revol&page=102"

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

# It's safer to use the exact column name for MFR rather than an index position
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

print(f"\n🔎 Accessing Search Page: {search_url}")

try:
    driver.get(search_url)
    
    # Wait a bit longer here since it's loading a massive page of products
    time.sleep(8) 

    soup = BeautifulSoup(driver.page_source, "lxml")
    
    # Look for the specific anchor tags containing the products
    products = soup.select('a.rps-product-container')

    for item in products:
        href = item.get("href")
        if href:
            full_link = href if href.startswith("http") else baseurl + href
            if full_link not in productlinks:
                productlinks.append(full_link)
                
except Exception as e:
    print(f"⚠️ Failed to load search page: {e}")

print("=" * 50)
print(f"✅ TOTAL UNIQUE LINKS GATHERED: {len(productlinks)}")
print("=" * 50)

if len(productlinks) == 0:
    print("⚠️ No links were found. The page might need more time to load or the JS structure changed.")

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
            mfr_xpath = '//div[contains(@class, "product__title")]//h2'
            mfr_element = wait.until(EC.presence_of_element_located((By.XPATH, mfr_xpath)))
            raw_title = mfr_element.get_attribute("textContent").strip()
            
            # Extract only the MFR code right after "SKU: '"
            if "SKU: '" in raw_title:
                mfr = raw_title.split("SKU: '")[-1].strip()
                # Clean up any trailing quotes or parentheses
                mfr = mfr.replace("'", "").replace(")", "").strip()
            elif "SKU:" in raw_title:
                mfr = raw_title.split("SKU:")[-1].strip()
            else:
                print("❌ 'SKU:' format not found in title → Discarding Invalid Link")
                discarded_links_count += 1
                continue
                
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
            img_xpath = '//div[contains(@class, "product__media media media--transparent")]//img'
            img_element = wait.until(EC.presence_of_element_located((By.XPATH, img_xpath)))
            
            # Use 'src' or 'srcset' depending on how they load images
            image_url = img_element.get_attribute("src")
            if not image_url or "data:image" in image_url:
                image_url = img_element.get_attribute("data-src") or "N/A"
                if image_url.startswith("//"):
                    image_url = "https:" + image_url
        except TimeoutException:
            image_url = "N/A"

        # OVERVIEW / DESCRIPTION
        try:
            desc_xpath = '//div[contains(@class, "product__description")]'
            desc_element = wait.until(EC.presence_of_element_located((By.XPATH, desc_xpath)))
            overview = desc_element.get_attribute("textContent").strip()
            # Clean up excessive newlines/spacing
            overview = re.sub(r'\n+', '\n', overview)
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
        # Create a dictionary aligning with the exact headers in your REVOL_v4.xlsx
        new_row = {
            "Item No.": "N/A",
            "MFR": mfr,
            "Group Name": "REVOL",
            "Item Description": raw_title,
            "Image URL": image_url,
            "Overview": overview,
            "Length": "N/A",  # You can add custom scraping logic for these later if available on the new site!
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
        
        # Add to memory so we don't accidentally scrape it twice in one sitting
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
        wait = WebDriverWait(driver, 5)

    # =====================
    # SAVE NEW DATA BATCHES
    # =====================
    if len(new_data_scraped) > 0 and len(new_data_scraped) % save_interval == 0:
        # Convert our new data into a dataframe and append it to the old dataframe
        new_df = pd.DataFrame(new_data_scraped)
        combined_df = pd.concat([df, new_df], ignore_index=True)
        # Drop the temporary clean column before saving
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
print(f"Links skipped (Already in Spreadsheet): {skipped_mfr_count}")
print(f"Brand new products actively scraped:    {len(new_data_scraped)}")
print(f"Final data saved to:                    {excel_path}")
print("==================================================")

driver.quit()