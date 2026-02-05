import requests
from bs4 import BeautifulSoup

baseurl = 'https://shop.mohd.it/en/brands/broggi.html'

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36'
}

r = requests.get('https://shop.mohd.it/en/brands/broggi.html')
soup = BeautifulSoup(r.content, 'lxml')


productlist = soup.find_all('div', class_='ProductCard_product__r7RXg')

productlinks = []  

for ProductCard_product__r7RXg in productlist:
    for link in ProductCard_product__r7RXg.find_all('a', href=True):
        print(link['href'])
    