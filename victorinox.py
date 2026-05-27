import time
import pandas as pd
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException

# --- CONFIGURATION ---
BASE_URL = "https://www.restaurantsupply.com/collections/victorinox?page={}"
TOTAL_PAGES = 23 # Change to 1 or 2 for initial testing!
OUTPUT_FILE = "victorinox.xlsx"
SAVE_INTERVAL = 5 # Save to Excel every 5 scraped products

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
    
    # uc.Chrome automatically patches the driver to bypass passive bot detection
    driver = uc.Chrome(options=options)
    driver.set_page_load_timeout(30)
    return driver

# --- MAIN SCRAPER ---
def main():
    driver = start_browser()
    wait = WebDriverWait(driver, 10)
    
    product_links_set = set()
    scraped_data_list = []
    
    print("="*50)
    print("PHASE 1: GATHERING PRODUCT LINKS")
    print("="*50)
    
    try:
        # Loop through pages to get links
        for page in range(1, TOTAL_PAGES + 1):
            driver.get(BASE_URL.format(page))
            try:
                # Wait for the result grid
                wait.until(EC.presence_of_element_located((By.CLASS_NAME, "ss__results")))
                
                selector = "article.ss__result .ss__result__image-wrapper a"
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                
                for el in elements:
                    href = el.get_attribute('href')
                    if href:
                        product_links_set.add(href)
                
                print(f"Page {page}/{TOTAL_PAGES}: Scraped links. Total unique links so far: {len(product_links_set)}")
            except Exception as e:
                print(f"Error gathering links on page {page}: {e}")
                
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
                
                # Core Details
                item_data['Item Name'] = get_text_safe(driver, By.CSS_SELECTOR, "h1.product-title.h5")
                item_data['Mfr Code'] = get_text_safe(driver, By.CSS_SELECTOR, ".product-vendor-sku .product-mfg__value")
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
                
                # Terminal Output
                print(f"    -> Scraped: {item_data.get('Item Name', 'Unknown')}")
                print(f"    -> MFR: {item_data.get('Mfr Code')} | Item#: {item_data.get('Item No.')} | UPC: {item_data.get('UPC No.')}")

            except TimeoutException:
                print(f"    ⚠️ TIMEOUT: Page took too long to load or elements missing.")
                item_data['Item Name'] = "ERROR: Page Load Timeout"
            
            # --- FATAL ERROR RECOVERY (The memory leak bypass) ---
            except Exception as e:
                print(f"    ⚠️ FATAL BROWSER ERROR on {link}")
                print(f"    Error Details: {e}")
                print("    🔄 Restarting the browser to clear memory and continue...")
                item_data['Item Name'] = f"ERROR: {e}"
                
                try:
                    driver.quit() 
                except:
                    pass
                
                # Boot it back up and re-establish the wait variable
                driver = start_browser()
                wait = WebDriverWait(driver, 10)
            
            # Add the completed item to our master list
            scraped_data_list.append(item_data)
            
            # Save Checkpoint every 5 items
            if index % SAVE_INTERVAL == 0:
                pd.DataFrame(scraped_data_list).to_excel(OUTPUT_FILE, index=False)
                print(f"    💾 [SAVED] Checkpoint updated in {OUTPUT_FILE} (Rows: {index})")
                
    finally:
        try:
            driver.quit()
        except:
            pass
        
        # Final Save
        if scraped_data_list:
            pd.DataFrame(scraped_data_list).to_excel(OUTPUT_FILE, index=False)
            print("\n" + "="*50)
            print(f"🎉 SCRAPE COMPLETE. Final data saved to {OUTPUT_FILE}")
            print("="*50)

if __name__ == "__main__":
    main()