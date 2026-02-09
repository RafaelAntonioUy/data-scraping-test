import requests
import re
from bs4 import BeautifulSoup

#baseurl = 'https://www.intergastro.com/brands/broggi/'

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36'
}

BASE_URL = "https://www.intergastro.com"

productlinks = set()  

for x in range(1, 20):
    
    r = requests.get(f'https://www.intergastro.com/brands/broggi/Page{x}/', headers=headers)
    soup = BeautifulSoup(r.content, 'lxml')
    productlist = soup.find_all('div', class_='product-list-item col-md-4 col-xs-6 grid-view')

    for item in productlist:
        a = item.find('a', href=True)
        if not a:
            continue

        href = a['href'].strip()

        # only keep real product pages
        if "ViewProduct-Show" in href:
            if href.startswith("/"):
                href = BASE_URL + href
            productlinks.add(href)


for link in productlinks:
    r = requests.get(link, headers=headers)
    soup = BeautifulSoup(r.content, 'lxml')

    brand_tag = soup.find('div', class_='product-brand')
    name_tag = soup.find('h1', class_='product-name')
    mfr_tag = soup.find('li', class_='ish-ca-type')
    img_container = soup.find('div', class_='product-image-container')
    breadcrumb_div = soup.find('div', class_='breadcrumbs row')

    brand = brand_tag.text.strip() if brand_tag else None
    name = name_tag.text.strip() if name_tag else None
    mfr = mfr_tag.text.strip() if mfr_tag else None

    img_url = (
        img_container.find('img')['src']
        if img_container and img_container.find('img')
        else None
    )

    category = (
        " > ".join(a.text.strip() for a in breadcrumb_div.find_all('a'))
        if breadcrumb_div else None
    )

    broggi = {
        'brand': brand,
        'name': name,
        'manufacturer': mfr,
        'image_url': img_url,
        'category': category
    }

    print(
    "{\n"
    f"  'brand': {broggi['brand']!r},\n"
    f"  'name': {broggi['name']!r},\n"
    f"  'manufacturer': {broggi['manufacturer']!r},\n"
    f"  'image_url': {broggi['image_url']!r},\n"
    f"  'category': {broggi['category']!r}\n"
    "}\n"
)


"""for link in productlinks:
    r = requests.get(link, headers=headers)
    soup = BeautifulSoup(r.content, 'lxml')
    brand = soup.find('div', class_='product-brand').text.strip()
    name = soup.find('h1', class_='product-name').text.strip()
    mfr = soup.find('li', class_='ish-ca-type').text.strip()
    img_url = soup.find('div', class_='product-image-container').find('img').get('src')
    category = soup.find_all('div', class_='breadcrumbs row').find_all('a').text.strip()

    broggi = {
        'brand': brand,
        'name': name,
        'manufacturer': mfr,
        'image_url': img_url,
        'category': category
    }
    print(broggi)"""



#print (len(productlinks))
#print(*productlinks, sep='\n')
    