import time
import os
import pandas as pd
from urllib.parse import urljoin
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# =========================
# SETTINGS
# =========================

excel_path = "ROBOT_COUPE_V2.xlsx"
baseurl = "https://www.partstown.com"
total_pages = 224
save_interval = 5

# =========================
# LOAD EXCEL & EXISTING DATA
# =========================

print("Loading existing data...")
try:
    df = pd.read_excel(excel_path)
    # Extract the Mfr column, drop empty rows, convert to string, and strip spaces
    existing_mfrs = set(df["Mfr Catalog No."].dropna().astype(str).str.strip())
    print(f"✅ Excel Loaded: {len(df)} rows.")
    print(f"✅ Found {len(existing_mfrs)} previously scraped MFRs. Will skip these.")
except FileNotFoundError:
    print(f"⚠️ Could not find {excel_path}. Starting a brand new spreadsheet.")
    df = pd.DataFrame()
    existing_mfrs = set()

# =========================
# HELPER FUNCTIONS
# =========================

def start_stealth_browser():
    options = uc.ChromeOptions()
    options.add_argument("--window-size=1920,1080")
    options.page_load_strategy = 'eager'
    prefs = {"profile.managed_default_content_settings.images": 2}
    options.add_experimental_option("prefs", prefs)
    driver = uc.Chrome(options=options, version_main=145)
    return driver

# =========================
# SELENIUM SETUP
# =========================

print("\nLaunching stealth browser...")
driver = start_stealth_browser()
wait = WebDriverWait(driver, 8) 

# =========================
# PHASE 1: COLLECT PRODUCT LINKS
# =========================

productlinks = []

print(f"\n🚀 Starting link extraction for {total_pages} pages on Parts Town...\n")

for page_num in range(total_pages):
    url = f"{baseurl}/b/robot-coupe?page={page_num}"
    
    try:
        driver.get(url)
        
        if page_num == 0:
            print("\n*** IMPORTANT ***")
            print("Look at the browser window. Clear any 'Verify you are human' checks.")
            print("Waiting 15 seconds...\n")
            time.sleep(15)

        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "ul.js-parts-listing-holder")))
        
        selector = "li.js-product-item a.name"
        product_elements = driver.find_elements(By.CSS_SELECTOR, selector)
        
        if len(product_elements) == 0:
            product_elements = driver.find_elements(By.CSS_SELECTOR, "li.js-product-item div.details a")
        
        if not product_elements:
            print(f"⚠️ No products found on page {page_num}. Site might be blocking us.")
            time.sleep(2)
            continue
        
        page_links_count = 0
        for element in product_elements:
            href = element.get_attribute('href')
            if href:
                full_url = urljoin(baseurl, href)
                if full_url not in productlinks:
                    productlinks.append(full_url)
                    page_links_count += 1
                
        print(f"📄 Page {page_num + 1}/{total_pages} scanned | Found {page_links_count} new links")
                
    except TimeoutException:
        print(f"⚠️ Timeout on page {page_num}. Skipping to next...")
        time.sleep(5) 
    except Exception as e:
        print(f"⚠️ Failed to load page {page_num}: {e}")
    
    time.sleep(1)

print("\n✅ TOTAL UNIQUE LINKS TO CHECK:", len(productlinks))

# =========================
# PHASE 2: SCRAPE PRODUCTS
# =========================

total_links_visited = 0
new_data_scraped = []
skipped_mfr_count = 0

print("\n🚀 Starting individual product data extraction...\n")

for link in productlinks:
    total_links_visited += 1
    print(f"\n==================================================")
    print(f"🌐 Link ({total_links_visited}/{len(productlinks)}): {link}")

    try:
        driver.get(link)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.product-block.product-info")))
        
        # --- 1. FAST MFR CHECK ---
        mfr_code = "Not Found"
        try:
            mfr_selector = ".product-block.product-info .product__row .product__cell.product__val span[itemprop='productID']"
            mfr_element = driver.find_element(By.CSS_SELECTOR, mfr_selector)
            mfr_code = mfr_element.text.strip()
        except NoSuchElementException:
            pass

        # --- 2. THE SKIP LOGIC ---
        if mfr_code in existing_mfrs:
            print(f"⏭️ MATCH FOUND IN EXCEL ('{mfr_code}') -> Already scraped! Discarding link & Skipping...")
            skipped_mfr_count += 1
            continue
            
        print(f"⏳ NEW PRODUCT DETECTED ('{mfr_code}') -> Scraping remaining details...")

        # --- 3. EXTRACT IMAGE URL ---
        try:
            sirv_element = driver.find_element(By.CSS_SELECTOR, "div.product-gallery div.Sirv")
            base_img_url = sirv_element.get_attribute("data-src")
            
            if base_img_url:
                image_url = base_img_url + "?thumb&image.rules=G0}&w=500"
            else:
                image_url = "No data-src found"
        except NoSuchElementException:
            image_url = "Not Found"

        print("\n[ NEW SCRAPED DATA ]")
        print(f"MFR Code:   {mfr_code}")
        print(f"Image URL:  {image_url}")
        print("-" * 50)

        # =====================
        # PREPARE NEW ROW
        # =====================
        new_row = {
            "Item No.": "",
            "Mfr Catalog No.": mfr_code,
            "Group Name": "ROBOT COUPE",
            "Item Description": "",
            "Image URL": image_url
        }
        
        new_data_scraped.append(new_row)
        existing_mfrs.add(mfr_code) # Add to memory so we don't duplicate it in the same run

    except Exception as e:
        print(f"\n⚠️ FATAL BROWSER ERROR on {link}")
        print(f"Error Details: {e}")
        print("🔄 Restarting the browser to clear memory and continue...")
        
        try:
            driver.quit() 
        except:
            pass
            
        driver = start_stealth_browser()
        wait = WebDriverWait(driver, 8)

    # =====================
    # SAVE NEW DATA BATCHES
    # =====================
    if len(new_data_scraped) > 0 and len(new_data_scraped) % save_interval == 0:
        new_df = pd.DataFrame(new_data_scraped)
        if not df.empty:
            combined_df = pd.concat([df, new_df], ignore_index=True)
        else:
            combined_df = new_df
            
        combined_df.to_excel(excel_path, index=False)
        print(f"💾 Progress auto-saved to {excel_path} (Added {len(new_data_scraped)} new items)")
        
    time.sleep(1.5)

# =========================
# FINAL SAVE & STATISTICS
# =========================

if len(new_data_scraped) > 0:
    new_df = pd.DataFrame(new_data_scraped)
    if not df.empty:
        combined_df = pd.concat([df, new_df], ignore_index=True)
    else:
        combined_df = new_df
    combined_df.to_excel(excel_path, index=False)

print("\n==================================================")
print("🎉 SCRAPING COMPLETE - FINAL STATISTICS")
print("==================================================")
print(f"Total links visited/checked:            {total_links_visited}")
print(f"Links discarded (Already in Excel):     {skipped_mfr_count}")
print(f"Brand new products actively appended:   {len(new_data_scraped)}")
print(f"Final data saved to:                    {excel_path}")
print("==================================================")

try:
    driver.quit()
except OSError:
    pass 

os._exit(0)