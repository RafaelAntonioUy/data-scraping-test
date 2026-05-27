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

excel_path = "REVOL_v3.xlsx"  # File to read progress from and save to
baseurl = "https://www.restaurantsupply.com"

total_pages = 55
save_interval = 5

# =========================
# HELPER FUNCTIONS
# =========================

def extract_number(text):
    """Extract numeric value from string for volume calculation"""
    if not text or text == "N/A" or text == "Not Found":
        return None
    nums = re.findall(r"[\d.]+", text)
    return float(nums[0]) if nums else None

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
# LOAD EXISTING PROGRESS
# =========================

if os.path.exists(excel_path):
    df_existing = pd.read_excel(excel_path)
    scraped_data = df_existing.to_dict('records')
    # Create a fast lookup set of MFRs already in the file
    existing_mfrs = set(df_existing["MFR"].dropna().astype(str).str.strip())
    print(f"✅ Loaded existing progress: {len(existing_mfrs)} items already scraped.")
else:
    scraped_data = []
    existing_mfrs = set()
    print("⚠️ No existing progress found. Starting fresh.")

# =========================
# SELENIUM SETUP & LINK COLLECTION
# =========================

driver = start_browser()
wait = WebDriverWait(driver, 5)

productlinks = []

# (Note: In a massive scrape, you could also cache these links to a text file so you don't 
# have to re-scrape the pagination pages every time, but this will work fine for now!)
for page in range(1, total_pages + 1):
    url = f"{baseurl}/collections/revol?page={page}"
    print(f"\n🔎 Scraping page {page}")

    try:
        driver.get(url)
        time.sleep(4) 

        soup = BeautifulSoup(driver.page_source, "lxml")
        products = soup.select('a[href*="/products/"]')

        for item in products:
            href = item.get("href")
            if href:
                full_link = baseurl + href
                if full_link not in productlinks:
                    productlinks.append(full_link)
    except Exception as e:
        print(f"⚠️ Failed to load page {page}: {e}")

print("\n✅ TOTAL LINKS TO CHECK:", len(productlinks))

# =========================
# SCRAPE PRODUCTS
# =========================

checked_count = 0
skipped_count = 0
new_scraped_count = 0

for link in productlinks:
    checked_count += 1
    print(f"\n==================================================")
    print(f"🌐 Link ({checked_count}/{len(productlinks)}): {link}")

    try:
        driver.get(link)
        
        # --- TABLE SPEC EXTRACTOR ---
        def get_table_spec(th_text):
            try:
                xpath = f'//div[@class="specs-container"]//table//tbody//tr[th[contains(text(), "{th_text}")]]/td'
                element = wait.until(EC.presence_of_element_located((By.XPATH, xpath)))
                return element.get_attribute("textContent").strip()
            except TimeoutException:
                return "N/A"

        # 1. SCRAPE MFR FIRST
        mfr = get_table_spec("Manufacturer Part")
        
        # 2. CHECK IF WE SHOULD SKIP
        if mfr in existing_mfrs and mfr != "N/A":
            print(f"⏭️ ALREADY SCRAPED '{mfr}' -> Skipping to save time!")
            skipped_count += 1
            continue

        print(f"⏳ New product found ('{mfr}'). Scraping details...")

        # Get the rest of the Specs from Table
        ean_code = get_table_spec("UPC")
        length = get_table_spec("Depth")
        width = get_table_spec("Width")
        height = get_table_spec("Height")
        shape = get_table_spec("Shape")
        material = get_table_spec("Material")

        # --- 3. Image URL ---
        try:
            img_xpath = '//div[contains(@class, "pmslider-slide--inner")]//img'
            img_element = wait.until(EC.presence_of_element_located((By.XPATH, img_xpath)))
            image_url = img_element.get_attribute("src")
        except TimeoutException:
            image_url = "N/A"

        # --- 4. Overview ---
        try:
            overview_xpath = '(//div[contains(@class, "product-description-content")]//p[string-length(normalize-space(.)) > 15])[1]'
            overview_element = wait.until(EC.presence_of_element_located((By.XPATH, overview_xpath)))
            overview = overview_element.get_attribute("textContent").strip()
        except TimeoutException:
            try:
                js_script = """
                    let descDiv = document.querySelector('div[class*="product-description-content"]');
                    if (descDiv) {
                        let ps = descDiv.querySelectorAll('p');
                        for (let p of ps) {
                            if (p.textContent.trim().length > 15) return p.textContent.trim();
                        }
                    }
                    return 'N/A';
                """
                overview = driver.execute_script(js_script)
            except Exception:
                overview = "N/A"

        # --- 5. Features ---
        try:
            features_xpath = '(//div[contains(@class, "metafield-rich_text_field")]//h2)[5]/following-sibling::ul[1]/li'
            wait.until(EC.presence_of_element_located((By.XPATH, features_xpath)))
            
            feature_elements = driver.find_elements(By.XPATH, features_xpath)
            features_list = [li.get_attribute("textContent").strip() for li in feature_elements]
            features = ", ".join(features_list) if features_list else "N/A"
        except TimeoutException:
            features = "N/A"

        # --- 6. Volume Calculation ---
        L = extract_number(length)
        W = extract_number(width)
        H = extract_number(height)
        volume = round(L * W * H, 2) if (L and W and H) else "N/A"

        # =====================
        # TERMINAL OUTPUT
        # =====================
        print("\n[ SCRAPED DATA ]")
        print(f"MFR:        {mfr}")
        print(f"EAN Code:   {ean_code}")
        print(f"Image URL:  {image_url}")
        print(f"Length:     {length}")
        print(f"Width:      {width}")
        print(f"Height:     {height}")
        print("-" * 50)

        # =====================
        # APPEND TO DATA LIST
        # =====================
        row_data = {
            "MFR": mfr,
            "Image URL": image_url,
            "Overview": overview,
            "Length": length,
            "Width": width,
            "Height": height,
            "Shape": shape,
            "Material": material,
            "Features": features,
            "Volume": volume,
            "Capacity": "N/A",
            "Edge Style": "N/A",
            "EAN Code": ean_code,
            "Pattern": "N/A",
            "Barcode": "N/A",
            "Product Link": link
        }
        
        scraped_data.append(row_data)
        existing_mfrs.add(mfr) # Add to memory so we don't scrape it twice in one session
        new_scraped_count += 1

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
    # SAVE PERIODICALLY (Only counts actual new scrapes)
    # =====================
    if new_scraped_count > 0 and new_scraped_count % save_interval == 0:
        pd.DataFrame(scraped_data).to_excel(excel_path, index=False)
        print(f"💾 Progress saved to {excel_path} (New items this session: {new_scraped_count})")

# =========================
# FINAL SAVE
# =========================

if new_scraped_count > 0:
    pd.DataFrame(scraped_data).to_excel(excel_path, index=False)

print("\n======================")
print("🎉 ALL DONE!")
print(f"Total links checked: {checked_count}")
print(f"Total links skipped (already scraped): {skipped_count}")
print(f"Total NEW links scraped this session: {new_scraped_count}")
print(f"Final data saved to: {excel_path}")
print("======================")

driver.quit()