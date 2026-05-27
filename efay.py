import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import urllib.parse
import json
import time
import pandas as pd
import os

# --- CONFIGURATION ---
BASE_URL = "https://www.kkh.biz"
SEARCH_URL_TEMPLATE = "https://www.kkh.biz/search?q=efay&_pos=1&_psq=efay&_ss=e&_v=1.0&page={}"
TOTAL_PAGES = 84
EXCEL_FILENAME = "efayv2.xlsx"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def get_all_product_links():
    """Phase 1: Scrapes all pagination pages using Selenium to gather dynamic links."""
    print("--- Phase 1: Gathering all KKH product links via Selenium ---")
    all_links = []
    
    options = webdriver.ChromeOptions()
    # options.add_argument('--headless') # Uncomment this if you don't want the browser to visibly open
    
    driver = webdriver.Chrome(options=options)

    for page in range(1, TOTAL_PAGES + 1):
        url = SEARCH_URL_TEMPLATE.format(page)
        try:
            driver.get(url)
            
            # Wait up to 10 seconds for the Globo Filter app to load the products
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "spf-product-card__inner"))
            )
            
            card_inners = driver.find_elements(By.CLASS_NAME, "spf-product-card__inner")
            
            for inner in card_inners:
                try:
                    a_tag = inner.find_element(By.TAG_NAME, 'a')
                    href = a_tag.get_attribute('href')
                    if href and href not in all_links:
                        all_links.append(href)
                except Exception:
                    continue
            
            if page % 5 == 0 or page == TOTAL_PAGES or page == 1:
                print(f"Scanned page {page}/{TOTAL_PAGES}... (Total links so far: {len(all_links)})")
            
            time.sleep(1) # Polite delay
            
        except Exception as e:
            print(f"Timeout or error on page {page}. Skipping.")
            continue

    driver.quit()
    print(f"Phase 1 Complete. Found {len(all_links)} total product links.\n")
    return all_links

def scrape_product_details(url):
    """Phase 2: Scrapes the details using BeautifulSoup for speed."""
    try:
        response = requests.get(url, headers=HEADERS)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        product_data = {
            "Product_URL": url,
            "Name": None,
            "Code": None,
            "Image_URL": None,
            "Overview": None
        }

        # 1. & 2. Get Product Name & Code
        title_div = soup.find('div', class_='product__title')
        if title_div:
            h1_tag = title_div.find('h1')
            if h1_tag:
                title_text = h1_tag.get_text(strip=True)
                product_data["Name"] = title_text
                
                # Split by '#' for the code
                if '#' in title_text:
                    product_data["Code"] = title_text.split('#')[-1].strip()
                else:
                    product_data["Code"] = title_text

        # 3. Get Image URL
        media_wrapper = soup.find('div', class_='product__media-wrapper')
        if media_wrapper:
            media_div = media_wrapper.find('div', class_=lambda c: c and 'product__media' in c)
            if media_div:
                img_tag = media_div.find('img')
                if img_tag:
                    raw_src = img_tag.get('src') or img_tag.get('data-src')
                    if raw_src:
                        if raw_src.startswith('//'):
                            product_data["Image_URL"] = "https:" + raw_src
                        else:
                            product_data["Image_URL"] = urllib.parse.urljoin(BASE_URL, raw_src)

        # 4. Get Overview
        desc_div = soup.find('div', class_=lambda c: c and 'product__description' in c and 'rte' in c)
        if desc_div:
            product_data["Overview"] = desc_div.get_text(separator=' ', strip=True)

        return product_data

    except Exception as e:
        print(f"Failed to scrape {url}: {e}")
        return None

def main():
    # --- Step 1: Safely Load Existing Excel File ---
    if os.path.exists(EXCEL_FILENAME):
        try:
            df_existing = pd.read_excel(EXCEL_FILENAME)
            print(f"--- Loaded existing '{EXCEL_FILENAME}' with {len(df_existing)} rows ---")
        except Exception as e:
            print(f"Error loading existing Excel file: {e}. Starting fresh.")
            df_existing = pd.DataFrame()
    else:
        print(f"--- '{EXCEL_FILENAME}' not found. A new one will be created ---")
        df_existing = pd.DataFrame()

    # --- Step 2: Get all links via Selenium ---
    links = get_all_product_links()
    if not links:
        print("No links found. Exiting.")
        return

    # --- Step 3: Scrape details via BS4 and save in batches ---
    print("\n--- Phase 2: Scraping details and saving to Excel ---")
    scraped_data_list = []
    
    for index, link in enumerate(links, start=1):
        print(f"\n[Scraping {index}/{len(links)}] {link}")
        
        data = scrape_product_details(link)
        if data:
            scraped_data_list.append(data)
            
            # Print to terminal to monitor progress
            print(json.dumps(data, indent=4, ensure_ascii=False))
        
        # Save to Excel every 5 items, OR if it is the very last item in the list
        if index % 5 == 0 or index == len(links):
            if scraped_data_list:
                df_new = pd.DataFrame(scraped_data_list)
                df_combined = pd.concat([df_existing, df_new], ignore_index=True)
                
                # --- ENFORCE COLUMN POSITIONS ---
                existing_cols = df_combined.columns.tolist()
                
                # Required Core Columns (A=1st, B=2nd, C=3rd, D=4th)
                core_cols = ["Product_URL", "Name", "Code", "Image_URL"]
                
                # Ensure they exist
                for c in core_cols + ["Overview"]:
                    if c not in existing_cols:
                        df_combined[c] = None
                        existing_cols.append(c)
                
                # Identify any remaining columns (like Specifications or Colour)
                remaining_cols = [c for c in existing_cols if c not in core_cols and c != "Overview"]
                
                # Grab whatever belongs in Column E (Index 4) as a buffer
                col_e = remaining_cols.pop(0) if remaining_cols else "Extra_Column"
                if col_e not in df_combined.columns:
                    df_combined[col_e] = None
                
                # Final Array Order: A(URL), B(Name), C(Code), D(Image), E(Buffer), F(Overview), G+(Rest)
                final_order = core_cols + [col_e, "Overview"] + remaining_cols
                df_combined = df_combined[final_order]
                
                df_combined.to_excel(EXCEL_FILENAME, index=False)
                print(f"\n---> SUCCESS: Master spreadsheet updated! Total rows now: {len(df_combined)} <---")
        
        time.sleep(1) # Crucial delay to avoid getting IP banned during BS4 requests

    print("\n--- Scraping Complete! ---")
    print(f"All new KKH data successfully appended to {EXCEL_FILENAME}.")

if __name__ == "__main__":
    main()