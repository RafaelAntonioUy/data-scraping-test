import pandas as pd
import time
import os
from urllib.parse import urljoin
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def scrape_pastrychefs_links_selenium(max_pages=67):
    base_domain = "https://www.pastrychefsboutique.com"
    all_links = []
    
    print(f"\n--- PHASE 1: STARTING LINK SCRAPER ({max_pages} Pages) ---")
    
    chrome_options = Options()
    # chrome_options.add_argument("--headless") # Comment out to watch it work
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
    
    driver = webdriver.Chrome(options=chrome_options)
    wait = WebDriverWait(driver, 10)
    
    pages_scraped = 0
    
    try:
        for page in range(1, max_pages + 1):
            url = f"{base_domain}/module/ambjolisearch/jolisearch?s=broggi&page={page}"
            print(f"Scraping Links from Page {page}...")
            
            try:
                driver.get(url)
                wait.until(EC.presence_of_element_located((By.ID, 'js-product-list')))
                driver.execute_script("window.scrollBy(0, 1000);")
                time.sleep(1) 
                
                css_selector = '#js-product-list div.products.row div.js-product article.product-miniature div.thumbnail-container div.thumbnail-top a'
                link_elements = driver.find_elements(By.CSS_SELECTOR, css_selector)
                
                if not link_elements:
                    print(" -> No products found on this page. Reached the end!")
                    break
                    
                links_found_on_page = 0
                for a_tag in link_elements:
                    href = a_tag.get_attribute('href')
                    if href:
                        full_link = urljoin(base_domain, href)
                        if full_link not in all_links:
                            all_links.append(full_link)
                            links_found_on_page += 1
                
                pages_scraped += 1
                
            except Exception as e:
                print(f" -> Failed to retrieve page {page}. Error: {e}")
                break
    finally:
        driver.quit()

    print(f"\n[SUCCESS] Total Unique Links Scraped: {len(all_links)}\n")
    return all_links


def scrape_details_and_save_selenium(product_links):
    print("--- PHASE 2: SCRAPING DETAILS & SAVING TO EXCEL ---")
    
    output_filename = "BROGGI_v2.xlsx"
    columns = [
        "Item No.", 
        "Mfr Catalog No.", 
        "Group Name", 
        "Item Description", 
        "Short Description", 
        "Image URL",       
        "Product URL"      
    ]
    
    # --- LOAD EXISTING DATA ---
    existing_mfrs = set()
    if os.path.exists(output_filename):
        try:
            df = pd.read_excel(output_filename)
            if "Mfr Catalog No." in df.columns:
                existing_mfrs = set(df["Mfr Catalog No."].dropna().astype(str).str.strip())
                print(f"[INFO] Loaded {len(existing_mfrs)} existing Mfr Codes from {output_filename}.\n")
            else:
                print(f"[WARNING] 'Mfr Catalog No.' column not found. Starting fresh.")
        except Exception as e:
            print(f"[ERROR] Could not read {output_filename}: {e}. Starting fresh.")
            df = pd.DataFrame(columns=columns)
    else:
        print(f"[INFO] {output_filename} not found. A new file will be created.\n")
        df = pd.DataFrame(columns=columns)

    # Set up Chrome for Detail Scraping
    chrome_options = Options()
    # chrome_options.add_argument("--headless")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
    
    driver = webdriver.Chrome(options=chrome_options)
    wait = WebDriverWait(driver, 10)

    # Trackers for the terminal output
    discarded_count = 0
    saved_count = 0

    try:
        for i, url in enumerate(product_links):
            print(f"\n[{i+1}/{len(product_links)}] Processing: {url}")
            
            mfr_code = ""
            img_url = ""

            try:
                driver.get(url)
                
                # --- 1. EXTRACT MFR CODE FIRST ---
                try:
                    ref_span = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'div.product-reference span')))
                    mfr_code = ref_span.text.strip()
                except Exception:
                    pass

                # --- 2. CHECK IF CODE ALREADY EXISTS ---
                if mfr_code and mfr_code in existing_mfrs:
                    print(f"   -> [DISCARDED] Mfr Code '{mfr_code}' already exists in spreadsheet.")
                    discarded_count += 1
                    continue # Instantly skip the rest of this loop iteration!

                # --- 3. IF NEW, EXTRACT THE REST (IMAGE URL) ---
                try:
                    img_tag = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'div.product-cover img')))
                    raw_src = img_tag.get_attribute('src')
                    if raw_src:
                        img_url = urljoin(url, raw_src)
                except Exception:
                    pass

            except Exception as e:
                print(f"   -> Failed to load page in browser. Error: {e}")

            # --- TERMINAL OUTPUT ---
            print(f"   -> [NEW PRODUCT SCRAPED]")
            print(f"      Mfr Code : {mfr_code if mfr_code else 'Not Found'}")
            print(f"      Image URL: {img_url if img_url else 'Not Found'}")

            # --- APPEND NEW DATA ---
            new_row = {
                "Item No.": "",
                "Mfr Catalog No.": mfr_code,
                "Group Name": "BROGGI", # Hardcoding since it's the Broggi brand
                "Item Description": "",
                "Short Description": "",
                "Image URL": img_url,
                "Product URL": url
            }
            
            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
            
            if mfr_code:
                existing_mfrs.add(mfr_code)
                
            saved_count += 1

            # --- SAVE EVERY 5 NEW PRODUCTS ---
            if saved_count > 0 and saved_count % 5 == 0:
                df.to_excel(output_filename, index=False)
                print(f"   [+] Auto-saved! ({saved_count} new items added to {output_filename})")
                
    finally:
        driver.quit()
        # Final save to catch any remainders
        if saved_count > 0:
            df.to_excel(output_filename, index=False)
            print(f"\n   [+] Final save complete! Data written to {output_filename}")

    # --- FINAL REPORT ---
    print(f"\n--- SCRAPING SESSION COMPLETE ---")
    print(f"Total Links Processed : {len(product_links)}")
    print(f"Total Links Discarded : {discarded_count}")
    print(f"Total New Items Saved : {saved_count}")

if __name__ == "__main__":
    # Ensure your BROGGI_v2.xlsx is in the exact same folder as this script
    links = scrape_pastrychefs_links_selenium(max_pages=67)
    
    if links:
        scrape_details_and_save_selenium(links)
    else:
        print("No links were found to scrape.")