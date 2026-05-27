import os
import time
import pandas as pd
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException

# --- CONFIGURATION ---
BASE_URL = "https://www.restaurantsupply.com/collections/vollrath?page={}"
TOTAL_PAGES = 417 
OUTPUT_FILE = "vollrathV2.xlsx"
SAVE_INTERVAL = 5 # Save to Excel every X NEW products scraped
RESTART_INTERVAL = 100 # Restart browser every X NEW products to clear RAM

# --- HELPER FUNCTIONS ---
def get_text_safe(driver, by, selector):
    try:
        element = driver.find_element(by, selector)
        text = element.text.strip()
        if not text:
            text = element.get_attribute("textContent").strip()
        return text
    except NoSuchElementException:
        return "N/A"

def get_attribute_safe(driver, by, selector, attr):
    try:
        return driver.find_element(by, selector).get_attribute(attr)
    except NoSuchElementException:
        return "N/A"

def start_browser():
    """Helper function to start/restart the browser using undetected_chromedriver"""
    options = uc.ChromeOptions()
    options.add_argument('--window-size=1920,1080') # Crucial for desktop view
    
    # Force compatibility with your installed Chrome
    driver = uc.Chrome(options=options, version_main=146)
    driver.set_page_load_timeout(30)
    return driver

# --- MAIN SCRAPER ---
def main():
    # --- 0. LOAD EXISTING PROGRESS ---
    if os.path.exists(OUTPUT_FILE):
        df_existing = pd.read_excel(OUTPUT_FILE)
        scraped_data_list = df_existing.to_dict('records')
        if 'Mfr Code' in df_existing.columns:
            existing_mfrs = set(df_existing["Mfr Code"].dropna().astype(str).str.strip())
        else:
            existing_mfrs = set()
        print(f"✅ Loaded existing progress: {len(existing_mfrs)} items already scraped.")
    else:
        scraped_data_list = []
        existing_mfrs = set()
        print("⚠️ No existing progress found. Starting fresh.")

    # Initialize variables here so the finally block never crashes!
    new_items_count = 0
    skipped_count = 0
    product_links_set = set()
    all_product_links = []

    driver = start_browser()
    wait = WebDriverWait(driver, 10)
    
    print("\n" + "="*50)
    print("PHASE 1: GATHERING PRODUCT LINKS")
    print("="*50)
    
    try:
        # Loop through pages to get links
        for page in range(1, TOTAL_PAGES + 1):
            try:
                # MOVED: driver.get is inside the try block now to prevent fatal timeouts
                driver.get(BASE_URL.format(page))
                
                # Wait for the result grid
                wait.until(EC.presence_of_element_located((By.CLASS_NAME, "ss__results")))
                
                selector = "article.ss__result .ss__result__image-wrapper a"
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                
                for el in elements:
                    href = el.get_attribute('href')
                    if href:
                        product_links_set.add(href)
                
                print(f"Page {page}/{TOTAL_PAGES}: Scraped links. Total unique links so far: {len(product_links_set)}")
            
            except TimeoutException:
                print(f"    ⚠️ TIMEOUT on Phase 1 Page {page}. Moving to next page...")
            except Exception as e:
                print(f"    ⚠️ Error gathering links on page {page}: {e}")
                
        # Convert set back to list for iteration
        all_product_links = list(product_links_set)
        total_links = len(all_product_links)
        
        print("\n" + "="*50)
        print(f"PHASE 2: SCRAPING {total_links} PRODUCT DETAILS")
        print("="*50)

        # Loop through each gathered link
        for index, link in enumerate(all_product_links, start=1):
            print(f"\n==================================================")
            print(f"🌐 Link ({index}/{total_links}): {link}")
            
            item_data = {'Product URL': link}
            
            try:
                driver.get(link)
                
                # Wait for the SKU container to load
                wait.until(EC.presence_of_element_located((By.CLASS_NAME, "product-vendor-sku")))
                
                # --- 1. SCRAPE MFR CODE FIRST ---
                mfr_code = get_text_safe(driver, By.CSS_SELECTOR, ".product-vendor-sku .product-mfg__value")
                
                # --- 2. CHECK IF WE SHOULD SKIP ---
                if mfr_code != "N/A" and mfr_code in existing_mfrs:
                    print(f"    ⏭️ ALREADY SCRAPED MFR '{mfr_code}' -> Skipping to save time!")
                    skipped_count += 1
                    continue
                
                # --- 3. PROCEED WITH FULL SCRAPE ---
                item_data['Mfr Code'] = mfr_code
                item_data['Item Name'] = get_text_safe(driver, By.CSS_SELECTOR, "h1.product-title.h5")
                item_data['Item No.'] = get_text_safe(driver, By.CSS_SELECTOR, ".product-vendor-sku .product-sku__value")
                item_data['UPC No.'] = get_text_safe(driver, By.CSS_SELECTOR, ".product-vendor-sku .product-info__barcode-value")
                item_data['Image URL'] = get_attribute_safe(driver, By.CSS_SELECTOR, "div.pmslider-slide--inner img", "src")
                
                # Description
                try:
                    desc_element = driver.find_element(By.CSS_SELECTOR, ".product-media-additional-desktop .product-info__block--md")
                    item_data['Description'] = " ".join(desc_element.get_attribute("textContent").split())
                except NoSuchElementException:
                    item_data['Description'] = "N/A"
                    
                # Specifications Table (Dynamic Columns)
                try:
                    rows = driver.find_elements(By.CSS_SELECTOR, "div.specs-container table tbody tr")
                    for row in rows:
                        try:
                            key = row.find_element(By.TAG_NAME, "th").get_attribute("textContent").strip()
                            value = row.find_element(By.TAG_NAME, "td").get_attribute("textContent").strip()
                            if key and key not in item_data:
                                item_data[key] = value
                            elif key:
                                item_data[f"Spec_{key}"] = value
                        except NoSuchElementException:
                            pass
                except Exception:
                    pass
                
                # Terminal Output for successful new scrape
                print(f"    -> Scraped: {item_data.get('Item Name', 'Unknown')}")
                print(f"    -> MFR: {item_data.get('Mfr Code')} | Item#: {item_data.get('Item No.')} | UPC: {item_data.get('UPC No.')}")

                # Add to lists and update counts
                scraped_data_list.append(item_data)
                existing_mfrs.add(mfr_code)
                new_items_count += 1

            except TimeoutException:
                print(f"    ⚠️ TIMEOUT: Page took too long to load or elements missing.")
            
            # --- FATAL ERROR RECOVERY ---
            except Exception as e:
                print(f"    ⚠️ FATAL BROWSER ERROR on {link}")
                print(f"    Error Details: {e}")
                print("    🔄 Restarting the browser to clear memory and continue...")
                
                try:
                    driver.quit() 
                except:
                    pass
                
                driver = start_browser()
                wait = WebDriverWait(driver, 10)
            
            # --- SAVE PERIODICALLY (Only counts actual NEW scrapes) ---
            if new_items_count > 0 and new_items_count % SAVE_INTERVAL == 0:
                pd.DataFrame(scraped_data_list).to_excel(OUTPUT_FILE, index=False)
                print(f"    💾 [SAVED] Progress updated in {OUTPUT_FILE} (New Items: {new_items_count})")
            
            # --- PREVENTIVE RAM RESTART (Only counts actual NEW scrapes) ---
            if new_items_count > 0 and new_items_count % RESTART_INTERVAL == 0:
                print(f"\n    🧹 [RAM CLEANUP] Scraped {new_items_count} new items. Restarting browser to free up memory...")
                try:
                    driver.quit()
                except:
                    pass
                
                time.sleep(2) # Give the OS a second to fully clear the process
                driver = start_browser()
                wait = WebDriverWait(driver, 10)
                
    finally:
        try:
            driver.quit()
        except:
            pass
        
        # Final Save
        if new_items_count > 0:
            pd.DataFrame(scraped_data_list).to_excel(OUTPUT_FILE, index=False)
            
        print("\n" + "="*50)
        print("🎉 SCRAPE COMPLETE.")
        print(f"Total links processed: {len(all_product_links)}")
        print(f"Items skipped (already scraped): {skipped_count}")
        print(f"New items scraped this session: {new_items_count}")
        print(f"Final data saved to {OUTPUT_FILE}")
        print("="*50)

if __name__ == "__main__":
    main()