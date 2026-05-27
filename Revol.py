from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import re
import time

def scrape_entire_catalog():
    # Initialize the Chrome driver
    driver = webdriver.Chrome()
    wait = WebDriverWait(driver, 10)
    
    domain = "https://www.revol1768.com"
    base_url = f"{domain}/en-us/products/tableware"
    
    # =========================================================
    # STEP 1: Scrape Category Links
    # =========================================================
    print(f"Navigating to base link: {base_url}")
    driver.get(base_url)
    
    category_links = set()
    print("Extracting category links...")
    
    try:
        xpath_categories = (
            "//section[contains(@class, 'relative overflow-hidden w-full flex flex-col')]"
            "//div[contains(@class, 'flex max-lg:flex-col')]"
            "//div[@data-role='card-collection' and @data-type='normal']//a"
        )
        
        category_elements = wait.until(
            EC.presence_of_all_elements_located((By.XPATH, xpath_categories))
        )
        
        for elem in category_elements:
            link = elem.get_attribute("href")
            if link:
                category_links.add(link)
                
        print(f"Successfully found {len(category_links)} category links.\n")
        
    except Exception as e:
        print(f"Could not find category links. Error: {e}")
        driver.quit()
        return

    # =========================================================
    # STEP 2: Scrape Base Product Links from Categories
    # =========================================================
    base_product_links = set()
    
    print("Visiting categories to extract base product links...")
    for index, cat_link in enumerate(category_links, 1):
        try:
            driver.get(cat_link)
            
            xpath_products = "//div[contains(@class, 'flex flex-wrap gap-x-0.5 gap-y-6 lg:gap-6 my-6 w-full')]//a"
            
            product_elements = wait.until(
                EC.presence_of_all_elements_located((By.XPATH, xpath_products))
            )
            
            for elem in product_elements:
                p_link = elem.get_attribute("href")
                if p_link:
                    base_product_links.add(p_link)
                    
            print(f"[{index}/{len(category_links)}] Scraped base products from: {cat_link}")
            time.sleep(1.5) # Polite delay
            
        except Exception as e:
            print(f"[{index}/{len(category_links)}] No products found on {cat_link}. Skipping...")

    print(f"\nFound {len(base_product_links)} base products. Moving to variation discovery...\n")

    # =========================================================
    # STEP 3: Scrape All Size & Color Variations (The Matrix)
    # =========================================================
    all_final_product_links = set()
    
    print("Extracting all size and color variations for each product...")
    for index, base_product in enumerate(base_product_links, 1):
        print(f"[{index}/{len(base_product_links)}] Checking variations for base product...")
        
        # Queue system for the current base product
        visited_urls = set()
        urls_to_visit = [base_product]
        
        while urls_to_visit:
            current_url = urls_to_visit.pop(0)
            
            if current_url in visited_urls:
                continue
                
            driver.get(current_url)
            visited_urls.add(current_url)
            all_final_product_links.add(current_url) # Add to our master list
            
            try:
                xpath_inputs = "//div[@data-role='area-ecommerce']//input[@data-role='filter' and (@data-type='size' or @data-type='color')]"
                
                input_elements = wait.until(
                    EC.presence_of_all_elements_located((By.XPATH, xpath_inputs))
                )
                
                for elem in input_elements:
                    onclick_text = elem.get_attribute("onclick")
                    
                    if onclick_text:
                        match = re.search(r"changeSizeOrColor\(\s*'([^']+)'\s*\)", onclick_text)
                        if match:
                            url_path = match.group(1).strip()
                            full_url = domain + url_path
                            
                            # If it's a new combination, queue it up to be checked
                            if full_url not in visited_urls and full_url not in urls_to_visit:
                                urls_to_visit.append(full_url)
                                
                time.sleep(1) # Polite delay
                
            except Exception:
                # If a product has no size/color buttons, it just times out and passes silently
                pass 

    # =========================================================
    # STEP 4: Terminal Output
    # =========================================================
    print("\n" + "="*50)
    print(" SCRAPING COMPLETED SUCCESSFULLY")
    print("="*50)
    print(f"Base product links found:  {len(base_product_links)}")
    print(f"Total UNIQUE variations scraped: {len(all_final_product_links)}")
    print("="*50 + "\n")

    # Close the browser
    driver.quit()
    
    return all_final_product_links

if __name__ == "__main__":
    final_dataset = scrape_entire_catalog()