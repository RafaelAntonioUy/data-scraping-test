import requests
import re
import os
from bs4 import BeautifulSoup
import pandas as pd  

baseurl = 'https://www.intergastro.com/brands/broggi/'

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36'
}

productlinks = set()  

#1: Collect all product links
for x in range(1, 20):
    r = requests.get(f'https://www.intergastro.com/brands/broggi/Page{x}/', headers=headers)
    soup = BeautifulSoup(r.content, 'lxml')
    productlist = soup.find_all('div', class_='product-list-item col-md-4 col-xs-6 grid-view')
    for item in productlist:
        for link in item.find_all('a', href=True):
            productlinks.add(baseurl.rstrip('/') + link['href'] if link['href'].startswith('/') else link['href'])


#2: Scrape product details
results = []  

for link in productlinks:
    r = requests.get(link, headers=headers)
    soup = BeautifulSoup(r.content, 'lxml')

    brand_tag = soup.find('div', class_='product-brand')
    name_tag = soup.find('h1', class_='product-name')
    img_container = soup.find('div', class_='product-image-container')
    breadcrumb_div = soup.find('div', class_='breadcrumbs row')
    name = name_tag.text.strip() if name_tag else "N/A"
    desc_tag = soup.find('div', id='ShortDescription')

    if desc_tag:
        raw_text = desc_tag.get_text(" ", strip=True)
        clean_text = raw_text.replace('\xa0', ' ')
        clean_text = re.sub(r'\s+', ' ', clean_text)
        clean_text = re.sub(r'(Manufacturer Prod\.-ID:)', r'\n\1', clean_text)
        clean_text = re.sub(r'(Series:)', r'\n\1', clean_text)
        clean_text = re.sub(r'(model:)', r'\n\1', clean_text)
        clean_text = re.sub(r'(GTIN:)', r'\n\1', clean_text)
        clean_text = re.sub(r'(Dimensions:)', r'\n\1', clean_text)
        clean_text = re.sub(r'(depth:)', r'\n\1', clean_text)
        clean_text = re.sub(r'(Length \(Width\):)', r'\n\1', clean_text)

        product_description = clean_text.strip()
    else:
        product_description = "N/A"


    brand = "N/A"

    if brand_tag:
        raw_brand = brand_tag.get_text(separator=" ", strip=True)
        brand = raw_brand.replace("Brand:", "").strip()

    mfr = "N/A"  

    for li in soup.find_all('li', class_='ish-ca-type'):
        text = li.get_text(strip=True)
    
        if "Manufacturer Prod.-ID" in text:
            match = re.search(r'Manufacturer Prod\.-ID:\s*(\d+)', text)
            if match:
                mfr = match.group(1)
                break  

    img_url = (
        img_container.find('img')['src']
        if img_container and img_container.find('img')
        else "N/A"
    )

    category = (
        " > ".join(a.text.strip() for a in breadcrumb_div.find_all('a'))
        if breadcrumb_div else "N/A"
    )

    broggi = {
        'brand': brand,
        'name': name,
        'manufacturer': mfr,
        'image_url': img_url,
        'category': category,
        'sourceUrl': link,
        'scraped_from': baseurl,
        'description': product_description
    }

    # Print 
    print(
    "{\n"
    f"  'brand': {broggi['brand']!r},\n"
    f"  'name': {broggi['name']!r},\n"
    f"  'manufacturer': {broggi['manufacturer']!r},\n"
    f"  'image_url': {broggi['image_url']!r},\n"
    f"  'category': {broggi['category']!r}\n"
    f"  'sourceUrl': {broggi['sourceUrl']!r}\n"
    f"  'scraped_from': {broggi['scraped_from']!r}\n"
    f"  'description': {broggi['description']!r}\n"
    "}\n"
    )

    results.append(broggi)

#3: Export to Excel
df = pd.DataFrame(results)
df = df[
    [
        'brand',
        'manufacturer',   # Column B
        'name',           # Column C
        'image_url',
        'category',
        'sourceUrl',
        'scraped_from',
        'description'
    ]
]

df = df.drop_duplicates(subset=['name'])

excel_filename = 'Uy_RafaeAntonio_BROGGI_20260209.xlsx'

if os.path.exists(excel_filename):
    old_df = pd.read_excel(excel_filename)

    df = pd.concat([old_df, df], ignore_index=True)

    df = df.drop_duplicates(subset=['name'])

df.to_excel(excel_filename, index=False)
print(f"Data saved to {excel_filename}")