import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

def scrape_product_details(test_url):
    domain = "https://www.carlislefsp.com"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    print(f"Scraping product details from: {test_url}...\n")
    response = requests.get(test_url, headers=headers)
    
    if response.status_code != 200:
        print(f"Failed to fetch the URL. Status code: {response.status_code}")
        return

    soup = BeautifulSoup(response.text, 'html.parser')
    
    # --- 1. MFR Code ---
    mfr_code = "N/A"
    mfr_tag = soup.find('dd', class_='fsp_component-kvd-value', itemprop='model')
    if mfr_tag:
        mfr_code = mfr_tag.get_text(strip=True)

    # --- 2. Color Variants / Product Links ---
    # Finding the card container and extracting all hrefs within it
    color_links = []
    colors_container = soup.find('div', class_='fsp_component-card-container')
    if colors_container:
        for a_tag in colors_container.find_all('a', href=True):
            color_links.append(urljoin(domain, a_tag['href']))
    
    # Ensure unique links in case of duplicates
    color_links = list(set(color_links))

    # --- 3. Image URL ---
    image_url = "N/A"
    primary_image_div = soup.find('div', class_='fsp-cms-item-image-primary')
    if primary_image_div:
        # Looking for div containing 'easyzoom' in its class list
        easyzoom_div = primary_image_div.find('div', class_=lambda c: c and 'easyzoom' in c)
        if easyzoom_div:
            img_a_tag = easyzoom_div.find('a', href=True)
            if img_a_tag:
                image_url = urljoin(domain, img_a_tag['href'])

    # --- 4. Overview (Features) ---
    overview_features = []
    features_div = soup.find('div', class_='features public')
    if features_div:
        bullets_ul = features_div.find('ul', class_='bullets')
        if bullets_ul:
            for li in bullets_ul.find_all('li'):
                overview_features.append(li.get_text(strip=True))

    # --- 5. Specifications ---
    specifications = {}
    # Find tables that have 'fsp-cms-item-techspecs' in their classes
    spec_tables = soup.find_all('table', class_=lambda c: c and 'fsp-cms-item-techspecs' in c)
    
    for table in spec_tables:
        tbody = table.find('tbody')
        if tbody:
            for tr in tbody.find_all('tr'):
                th = tr.find('th')
                if th:
                    key = th.get_text(strip=True)
                    # Find all tds since some specs have US and Metric values (as seen in your image)
                    tds = tr.find_all('td')
                    # Extract text, using a space separator to handle inner tags like <abbr> nicely
                    values = [td.get_text(separator=" ", strip=True) for td in tds]
                    # Join multiple columns (like inch | cm) with a divider for clean output
                    specifications[key] = " | ".join(values)

    # ==========================================
    # OUTPUT TO TERMINAL
    # ==========================================
    print("="*60)
    print("PRODUCT DETAILS")
    print("="*60)
    
    print(f"MFR Code      : {mfr_code}")
    print(f"Image URL     : {image_url}")
    
    print("\n[ Color Variant Links ]")
    if color_links:
        for idx, link in enumerate(color_links, 1):
            print(f"  {idx}. {link}")
    else:
        print("  No alternative color links found (Single color).")
        
    print("\n[ Overview Features ]")
    if overview_features:
        for feature in overview_features:
            print(f"  - {feature}")
    else:
        print("  No features found.")
        
    print("\n[ Specifications ]")
    if specifications:
        for key, value in specifications.items():
            # Pad the key for clean alignment in the terminal
            print(f"  {key:<20}: {value}")
    else:
        print("  No specifications found.")
    print("="*60)

if __name__ == "__main__":
    test_link = "https://www.carlislefsp.com/dinnerware/ridge-dinnerware/5310338"
    scrape_product_details(test_link)