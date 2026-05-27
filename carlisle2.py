import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import pandas as pd
import time
import os

def save_to_excel(new_data_batch, filename="carlislev3.xlsx"):
    """Appends a new batch of data to an existing Excel file, or creates a new one."""
    if not new_data_batch:
        return

    new_df = pd.DataFrame(new_data_batch)

    if os.path.exists(filename):
        existing_df = pd.read_excel(filename)
        combined_df = pd.concat([existing_df, new_df], ignore_index=True)
        combined_df = combined_df.drop_duplicates(subset=['Product URL'], keep='last')
        combined_df.to_excel(filename, index=False)
        print(f"\n[💾 AUTO-SAVE] Appended {len(new_data_batch)} items. Total in file: {len(combined_df)}\n")
    else:
        new_df.to_excel(filename, index=False)
        print(f"\n[💾 AUTO-SAVE] Created {filename} and saved first {len(new_df)} items.\n")

def get_soup(url, headers, max_retries=3):
    """Helper function to fetch a URL with retries, exponential backoff, and higher timeouts."""
    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=headers, timeout=30)
            if response.status_code == 200:
                return BeautifulSoup(response.text, 'html.parser')
            else:
                print(f"    [!] Status {response.status_code} for {url}")
        except requests.exceptions.Timeout:
            print(f"    [!] Timeout (Attempt {attempt + 1}/{max_retries}) for {url}. Retrying...")
        except Exception as e:
            print(f"    [!] Error (Attempt {attempt + 1}/{max_retries}) for {url}: {e}")
        
        time.sleep(2 * (attempt + 1))
        
    print(f"    [!] FATAL: Failed to retrieve {url} after {max_retries} attempts. Skipping.")
    return None

def carlisle_master_scraper():
    # Put all the category URLs you want to scrape inside this list
    base_urls = [
        "https://www.carlislefsp.com/waste-and-material-handling",
        "https://www.carlislefsp.com/floor-brushes-and-brooms",
        "https://www.carlislefsp.com/mopping-solutions",
        "https://www.carlislefsp.com/squeegee-and-window-cleaning",
        "https://www.carlislefsp.com/handles",
        "https://www.carlislefsp.com/brushes-and-accessories",
        "https://www.carlislefsp.com/color-coded-products",
        "https://www.carlislefsp.com/equipment-and-foodservice",
        "https://www.carlislefsp.com/cabinets",
        "https://www.carlislefsp.com/traytops-and-accessories",
        "https://www.carlislefsp.com/dishware-and-disposables",
        "https://www.carlislefsp.com/dishware-and-disposables",
        "https://www.carlislefsp.com/induction-heating-systems",
        "https://www.carlislefsp.com/serving-systems",
        "https://www.carlislefsp.com/retherm-systems",
        "https://www.carlislefsp.com/serving-counters",
        "https://www.carlislefsp.com/refrigeration",
        "https://www.carlislefsp.com/dispensers-and-heaters",
        "https://www.carlislefsp.com/tray-delivery-carts",
        "https://www.carlislefsp.com/starter-stations-and-conveyors",
        "https://www.carlislefsp.com/racks"
        # Add as many links as you need here, wrapped in quotes and separated by commas!
    ] 
    
    domain = "https://www.carlislefsp.com"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    print("="*60)
    print("PHASE 1: GATHERING ALL FINAL PRODUCT (COLOR) LINKS")
    print("="*60)

    # --- 1. Get Collections from ALL Base URLs ---
    collection_links = []
    
    for base_url in base_urls:
        print(f"\nScanning Base URL: {base_url}")
        soup = get_soup(base_url, headers)
        if not soup:
            print(f"Failed to load {base_url}. Skipping to next.")
            continue

        headings_block = soup.find('div', id='block-fsp-cms-headings')
        found_collections = False
        
        if headings_block:
            cards = headings_block.find_all('div', class_='fsp_component-card fsp_component-headingscard')
            for card in cards:
                a_tag = card.find('a')
                if a_tag and 'href' in a_tag.attrs:
                    collection_links.append(urljoin(domain, a_tag['href']))
                    found_collections = True
        
        # Fallback: If a specific URL has no sub-collections, treat it as a collection page
        if not found_collections:
            print(f"  -> No sub-collections found. Treating this URL as a direct collection.")
            collection_links.append(base_url)
            
        time.sleep(1) # Brief pause between checking main categories

    print(f"\nTotal Collections found across all URLs: {len(collection_links)}")

    # --- 2. Get Base Products ---
    base_product_links = set()
    for col_url in collection_links:
        print(f"Scanning Collection for products: {col_url}")
        col_soup = get_soup(col_url, headers)
        if not col_soup: continue
        
        gallery = col_soup.find('div', class_='fsp-cms-product-chart-gallery')
        if gallery:
            items = gallery.find_all('li', class_='fsp_component-card fsp_component-itemcard')
            for item in items:
                a_tag = item.find('a')
                if a_tag and 'href' in a_tag.attrs:
                    base_product_links.add(urljoin(domain, a_tag['href']))
        
        time.sleep(1)

    print(f"Found {len(base_product_links)} Base Products. Now finding color variants...")

    # --- 3. Get Color Variants (Final Product Links) ---
    final_product_links = set()
    for idx, base_prod_url in enumerate(base_product_links, 1):
        if idx % 10 == 0:
            print(f"Scanning variant link {idx}/{len(base_product_links)}...")
            
        prod_soup = get_soup(base_prod_url, headers)
        if not prod_soup: continue
        
        colors_container = prod_soup.find('div', class_='fsp_component-card-container')
        found_colors = False
        
        if colors_container:
            for a_tag in colors_container.find_all('a', href=True):
                final_product_links.add(urljoin(domain, a_tag['href']))
                found_colors = True
        
        if not found_colors:
            final_product_links.add(base_prod_url)
            
        time.sleep(0.5)

    final_product_links = list(final_product_links)
    print(f"\nTOTAL UNIQUE PRODUCT/COLOR LINKS TO SCRAPE: {len(final_product_links)}")
    
    print("\n" + "="*60)
    print("PHASE 2: EXTRACTING DETAILS & SAVING")
    print("="*60)

    batch_data = [] 

    # --- 4. Detail Extraction Loop ---
    for idx, url in enumerate(final_product_links, 1):
        print(f"\n[{idx}/{len(final_product_links)}] Scraping Details: {url}")
        
        detail_soup = get_soup(url, headers)
        if not detail_soup:
            continue

        # A. MFR Code
        mfr_tag = detail_soup.find('dd', class_='fsp_component-kvd-value', itemprop='model')
        if not mfr_tag or not mfr_tag.get_text(strip=True):
            print("    [-] No MFR Code found. Skipping product.")
            continue 
            
        mfr_code = mfr_tag.get_text(strip=True)

        product_data = {
            "Product URL": url,
            "MFR Code": mfr_code,
            "Image URL": "N/A",
            "Overview": ""
        }

        # B. Image URL
        primary_image_div = detail_soup.find('div', class_='fsp-cms-item-image-primary')
        if primary_image_div:
            easyzoom_div = primary_image_div.find('div', class_=lambda c: c and 'easyzoom' in c)
            if easyzoom_div:
                img_a_tag = easyzoom_div.find('a', href=True)
                if img_a_tag:
                    product_data["Image URL"] = urljoin(domain, img_a_tag['href'])

        # C. Overview Features
        features_div = detail_soup.find('div', class_='features public')
        if features_div:
            bullets_ul = features_div.find('ul', class_='bullets')
            if bullets_ul:
                features = [li.get_text(strip=True) for li in bullets_ul.find_all('li')]
                product_data["Overview"] = "\n".join(f"• {f}" for f in features)

        # D. Specifications
        spec_tables = detail_soup.find_all('table', class_=lambda c: c and 'fsp-cms-item-techspecs' in c)
        for table in spec_tables:
            tbody = table.find('tbody')
            if tbody:
                for tr in tbody.find_all('tr'):
                    th = tr.find('th')
                    if th:
                        key = th.get_text(strip=True)
                        tds = tr.find_all('td')
                        values = [td.get_text(separator=" ", strip=True) for td in tds]
                        product_data[key] = " | ".join(values)

        print(f"    -> MFR Code: {product_data['MFR Code']}")
        print(f"    -> Specs Gathered: {len(product_data.keys()) - 4} attributes")

        batch_data.append(product_data)

        # --- 5. Auto-Save every 5 links & Clear the batch ---
        if len(batch_data) >= 5:
            save_to_excel(batch_data, "carlislev3.xlsx")
            batch_data.clear() 
            
        time.sleep(0.5) 

    # --- 6. Final Save ---
    if batch_data:
        print("\n" + "="*60)
        print("SCRAPING COMPLETE. PERFORMING FINAL SAVE...")
        print("="*60)
        save_to_excel(batch_data, "carlislev3.xlsx")
    
    print("Process Finished Successfully!")

if __name__ == "__main__":
    carlisle_master_scraper()