import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import pandas as pd
import time
import os

def scrape_robotcoupe_links(max_pages=51):
    base_domain = "https://www.robotcoupe-spares.co.uk"
    all_links = []
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    print(f"--- PHASE 1: Scrape Product Links ({max_pages} Pages) ---")
    
    pages_scraped = 0
    
    for page in range(1, max_pages + 1):
        start_val = (page - 1) * 25
        url = f"{base_domain}/keywordSearchResults.asp?Ref=&Prd=&Att=&ParentGrp=&Keyword=robot%20coupe&sort_dir=0-0-1&sort_column=19-29-6&childof=&Start={start_val}"
        print(f"Scraping Links from Page {page}...")
        
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            table = soup.find('table', id='productListTable')
            if not table:
                print(" -> No product table found. Reached the end!")
                break
                
            td_elements = table.find_all('td', class_='productListDescription')
            if not td_elements:
                print(" -> No products found on this page. Stopping.")
                break
                
            links_found_on_page = 0
            for td in td_elements:
                a_tag = td.find('a')
                if a_tag and a_tag.get('href'):
                    full_link = urljoin(base_domain, a_tag['href'])
                    if full_link not in all_links:
                        all_links.append(full_link)
                        links_found_on_page += 1
            
            pages_scraped += 1
            
            if links_found_on_page < 25:
                break
                
            time.sleep(0.2) 
            
        except requests.exceptions.RequestException as e:
            print(f" -> Failed to retrieve page. Error: {e}")
            break

    print(f"\n[SUCCESS] Total unique product links scraped: {len(all_links)}\n")
    return all_links


def scrape_details_and_save(product_links):
    print("--- PHASE 2: Scraping Details & Saving to Excel ---")
    
    output_filename = "ROBOT_COUPE_V2.xlsx"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    # --- LOAD EXISTING DATA TO PREVENT DUPLICATES ---
    print("Loading existing data...")
    try:
        df = pd.read_excel(output_filename)
        # Assuming the column name from your previous setup is "Mfr Catalog No."
        existing_mfrs = set(df["Mfr Catalog No."].dropna().astype(str).str.strip())
        print(f"✅ Excel Loaded: {len(df)} rows.")
        print(f"✅ Found {len(existing_mfrs)} previously scraped MFRs. Will skip these.\n")
    except FileNotFoundError:
        print(f"⚠️ Could not find {output_filename}. Starting a brand new spreadsheet.\n")
        # Define columns based on your previous ROBOT_COUPE_V2 structure
        columns = [
            "Item No.", 
            "Mfr Catalog No.", 
            "Group Name", 
            "Item Description", 
            "Image URL"
        ]
        df = pd.DataFrame(columns=columns)
        existing_mfrs = set()

    new_items_scraped = 0
    new_data_batch = []
    skipped_mfr_count = 0

    for i, url in enumerate(product_links):
        print(f"\n[{i+1}/{len(product_links)}] Processing: {url}")
        
        mfr_code = "Not Found"
        img_url = "Not Found"

        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

            # --- 1. EXTRACT MANUFACTURER CODE ---
            h2_tag = soup.find('h2', string=lambda text: text and "Robot Coupe Reference:" in text)
            if h2_tag:
                span_tag = h2_tag.find_next('span')
                if span_tag:
                    mfr_code = span_tag.get_text(strip=True)
            
            # --- 2. CHECK IF CODE ALREADY EXISTS ---
            if mfr_code in existing_mfrs and mfr_code != "Not Found":
                print(f"   -> [SKIPPED] Mfr Code '{mfr_code}' already exists in spreadsheet.")
                skipped_mfr_count += 1
                continue 

            print(f"   ⏳ NEW PRODUCT DETECTED ('{mfr_code}') -> Scraping remaining details...")

            # --- 3. EXTRACT IMAGE URL ---
            img_container = soup.find('div', id='productImageContainer')
            if img_container:
                a_tag = img_container.find('a', class_='centerImage magnify')
                if a_tag:
                    img_tag = a_tag.find('img')
                    if img_tag and img_tag.get('src'):
                        raw_src = img_tag.get('src')
                        img_url = urljoin(url, raw_src)

            # --- OUTPUT TERMINAL FEEDBACK ---
            print(f"   -> [SCRAPED] Mfr Code:  {mfr_code}")
            print(f"   -> [SCRAPED] Image URL: {img_url}")

            # --- PREPARE NEW ROW ---
            new_row = {
                "Item No.": "",
                "Mfr Catalog No.": mfr_code,
                "Group Name": "ROBOT COUPE",
                "Item Description": "",
                "Image URL": img_url
            }
            
            new_data_batch.append(new_row)
            
            if mfr_code != "Not Found":
                existing_mfrs.add(mfr_code)
                
            new_items_scraped += 1

        except requests.exceptions.RequestException as e:
            print(f"   -> Failed to load page. Error: {e}")
            continue

        # --- SAVE EVERY 5 NEW PRODUCTS ---
        if new_items_scraped > 0 and new_items_scraped % 5 == 0:
            new_df = pd.DataFrame(new_data_batch)
            if not df.empty:
                combined_df = pd.concat([df, new_df], ignore_index=True)
            else:
                combined_df = new_df
                
            combined_df.to_excel(output_filename, index=False)
            print(f"   [+] Auto-saved progress! (Appended {len(new_data_batch)} new items to {output_filename})")
            
            # Update the main dataframe and clear the batch
            df = combined_df 
            new_data_batch = []
            
        time.sleep(0.5) 

    # Final save for any remaining items in the batch
    if new_data_batch:
        new_df = pd.DataFrame(new_data_batch)
        if not df.empty:
            combined_df = pd.concat([df, new_df], ignore_index=True)
        else:
            combined_df = new_df
        combined_df.to_excel(output_filename, index=False)
        print(f"\n   [+] Final save complete! (Appended {len(new_data_batch)} remaining items to {output_filename})")

    print("\n==================================================")
    print("🎉 SCRAPING COMPLETE - FINAL STATISTICS")
    print("==================================================")
    print(f"Total links visited/checked:            {len(product_links)}")
    print(f"Links discarded (Already in Excel):     {skipped_mfr_count}")
    print(f"Brand new products actively appended:   {new_items_scraped}")
    print(f"Final data saved to:                    {output_filename}")
    print("==================================================")

if __name__ == "__main__":
    links = scrape_robotcoupe_links(max_pages=51)
    
    if links:
        scrape_details_and_save(links)
    else:
        print("No links were found to scrape.")