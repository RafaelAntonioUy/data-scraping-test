import time
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from webdriver_manager.chrome import ChromeDriverManager

# --- CONFIGURATION ---
BASE_URL = "https://www.restaurantsupply.com/collections/vollrath?page={}"
TOTAL_PAGES = 2 # Change this to 1 or 2 for initial testing!
OUTPUT_FILE = "vollrath.xlsx"
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

# --- MAIN SCRAPER ---
def main():
    # 1. Setup Chrome
    options = webdriver.ChromeOptions()
    
    # REMOVED: options.add_argument('--headless') 
    
    # Keep the window large so the desktop elements load properly
    options.add_argument('--window-size=1920,1080') 
    options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    
    all_product_links = []
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
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CLASS_NAME, "ss__results"))
                )
                
                selector = "article.ss__result .ss__result__image-wrapper a"
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                
                page_links = [el.get_attribute('href') for el in elements if el.get_attribute('href')]
                all_product_links.extend(page_links)
                
                print(f"Page {page}/{TOTAL_PAGES}: Scraped {len(page_links)} links. Total links so far: {len(all_product_links)}")
            except Exception as e:
                print(f"Error gathering links on page {page}: {e}")
                
        # Remove any duplicate links just in case
        all_product_links = list(set(all_product_links))
        total_links = len(all_product_links)
        
        print("\n" + "="*50)
        print(f"PHASE 2: SCRAPING {total_links} PRODUCT DETAILS")
        print("="*50)
        
        # Loop through each gathered link
        for index, link in enumerate(all_product_links, start=1):
            driver.get(link)
            
            # This dict will hold a single row's worth of data
            item_data = {'Product URL': link}
            
            try:
                # Wait for the SKU container (or title) to load
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CLASS_NAME, "product-vendor-sku"))
                )
                
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
                            # Prevent specs from overwriting core columns if they happen to share a name
                            if key and key not in item_data:
                                item_data[key] = value
                            elif key:
                                item_data[f"Spec_{key}"] = value
                        except NoSuchElementException:
                            pass
                except Exception:
                    pass
                
            except TimeoutException:
                item_data['Item Name'] = "ERROR: Page Load Timeout"
            except Exception as e:
                item_data['Item Name'] = f"ERROR: {e}"
            
            # Add the completed item to our master list
            scraped_data_list.append(item_data)
            
            # Terminal Output
            print(f"[{index}/{total_links}] Scraped: {item_data.get('Item Name', 'Unknown')}")
            print(f"    -> MFR: {item_data.get('Mfr Code')} | Item#: {item_data.get('Item No.')} | UPC: {item_data.get('UPC No.')}")
            
            # Save Checkpoint every 5 items
            if index % SAVE_INTERVAL == 0:
                df = pd.DataFrame(scraped_data_list)
                df.to_excel(OUTPUT_FILE, index=False)
                print(f"    [SAVED] Checkpoint updated in {OUTPUT_FILE} (Rows: {index})")
                
    finally:
        driver.quit()
        
        # Final Save (Catches any remaining items if the total wasn't perfectly divisible by 5)
        if scraped_data_list:
            df = pd.DataFrame(scraped_data_list)
            df.to_excel(OUTPUT_FILE, index=False)
            print("\n" + "="*50)
            print(f"SCRAPE COMPLETE. Final data saved to {OUTPUT_FILE}")
            print("="*50)

if __name__ == "__main__":
    main()