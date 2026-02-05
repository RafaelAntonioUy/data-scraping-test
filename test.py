import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import time

headers = {
    "User-Agent": "Mozilla/5.0"
}

# Example: Load product list (with MFR codes)
product_list = pd.read_excel("BROGGI.xlsx")

product_list.columns = product_list.columns.str.strip()

for index, row in product_list.iterrows():
    mfr_code = str(row["Mfr Catalog No."]).strip()
    product_name_ref = row["Short Description"]

    print("MFR:", mfr_code, "| Name:", product_name_ref)

    # Example search on shopdecor (change per site)
    search_url = f"https://shopdecor.com/search?q={mfr_code}"
    
    try:
        r = requests.get(search_url, headers=headers, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")

        # Find first product link
        product_link = soup.find("a", class_="product-item__title")

        if not product_link:
            print("Not found")
            continue

        product_url = "https://shopdecor.com" + product_link["href"]

        # Open product page
        r2 = requests.get(product_url, headers=headers)
        soup2 = BeautifulSoup(r2.text, "html.parser")

        # ---- SCRAPE DATA ----
        name = soup2.find("h1").text.strip()

        img = soup2.find("img", class_="product__media-image")["src"]

        desc = soup2.find("div", class_="product__description").text.strip()

        specs = soup2.find("div", class_="product__accordion-content").text.strip()

        results.append({
            "brand": "BROGGI",
            "product_name": name,
            "manufacturer_id": mfr_code,
            "product_url": product_url,
            "image_url": img,
            "availability": "In Stock",  # change if site shows it
            "category": "Tableware",      # adjust per product
            "product_description_overview": desc,
            "scraped_at": datetime.now().strftime("%Y-%m-%d"),
            "product_specs": specs
        })

        time.sleep(2)  # be polite

    except Exception as e:
        print("Error:", e)
        continue

# Save file
df = pd.DataFrame(results)
df.to_excel("Uy_Rafael_BROGGI_20260205.xlsx", index=False)
