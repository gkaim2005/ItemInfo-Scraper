import csv
import time
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from concurrent.futures import ThreadPoolExecutor, as_completed

def is_product_listed(driver, sku):
    """
    Quickly checks if the product page for the given SKU shows the expected product element.
    Returns True if the product is listed; otherwise, False.
    """
    url = f"https://www.iteminfo.com/product/{sku}"
    driver.get(url)
    try:
        # Use a short wait (5 seconds) for the product name element.
        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "#wrapper > div > div.container > div > div.col-xs-12.col-sm-12.col-md-9.col-lg-9.details-page > div > div.col-lg-7.col-md-7.col-sm-6.col-xs-12.wow.fadeInUp.product-section > div.hidden-xs > h1 > span"))
        )
        return True
    except Exception:
        return False

def get_product_details(driver, sku):
    # Construct the URL for the product page using the SKU.
    url = f"https://www.iteminfo.com/product/{sku}"
    driver.get(url)
    
    wait = WebDriverWait(driver, 15)
    time.sleep(2)
    
    product_name = ""
    description = ""
    specifications = ""
    main_image = ""

    # 1. Extract Product Name.
    try:
        product_name_elem = wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "#wrapper > div > div.container > div > div.col-xs-12.col-sm-12.col-md-9.col-lg-9.details-page > div > div.col-lg-7.col-md-7.col-sm-6.col-xs-12.wow.fadeInUp.product-section > div.hidden-xs > h1 > span"))
        )
        product_name = product_name_elem.text.strip()
    except Exception as e:
        print(f"Error getting product name for SKU {sku}: {e}")

    # 2. Extract Product Description.
    try:
        description_container = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".product-description"))
        )
        description_elem = description_container.find_element(By.CSS_SELECTOR, "span.ng-binding")
        description = description_elem.text.strip() if description_elem else "No description available."
        bullet_points = []
        try:
            bullet_elements = description_container.find_elements(By.CSS_SELECTOR, "ul.ng-binding li")
            bullet_points = [f"- {bullet.text.strip()}" for bullet in bullet_elements]
        except Exception:
            pass  # No bullet points found, ignore

        if bullet_points:
            description += "\n" + "\n".join(bullet_points)
    except Exception as e:
        print(f"Error getting description for SKU {sku}: {e}")


    # 3. Extract Specifications.
    try:
        details_elem = wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div#details"))
        )
        details_html = details_elem.get_attribute("outerHTML")
        soup = BeautifulSoup(details_html, "html.parser")
        sections = []
        # Find all accordion headers (which have class "accordionHead").
        headers = soup.select("a.accordionHead")
        for header in headers:
            # Get the section title.
            section_title = header.get_text(strip=True)
            # The content is in the next sibling div with class "accordion-body"
            content_div = header.find_next_sibling("div", class_="accordion-body")
            section_content = ""
            if content_div:
                # For each table row in this section, extract label and value.
                rows = content_div.select("table tbody tr")
                row_texts = []
                for row in rows:
                    cells = row.find_all("td")
                    if len(cells) >= 2:
                        label = cells[0].get_text(strip=True)
                        value = cells[1].get_text(strip=True)
                        row_texts.append(f"- {label}: {value}")
                    else:
                        row_texts.append(f"- {row.get_text(strip=True)}")
                section_content = "\n".join(row_texts)
            sections.append(f"{section_title}:\n{section_content}")
        specifications = "\n\n".join(sections)
    except Exception as e:
        print(f"Error getting specifications for SKU {sku}: {e}")

    # 5. Extract Main Product Image.
    try:
        image_elem = wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "a.main-product-images img.img-responsive.lazyOwl"))
        )
        main_image = image_elem.get_attribute("src")

        # Ensure proper URL formatting
        if main_image.startswith("//"):
            main_image = "https:" + main_image
    except Exception as e:
        print(f"Error getting main product image for SKU {sku}: {e}")

    return {
        "SKU": sku,
        "Product Name": product_name,
        "Description": description,
        "Specifications": specifications,
        "Main Image": main_image
    }

def process_sku(sku):
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    driver = webdriver.Chrome(options=chrome_options)
    try:
        # First check if the product is listed.
        if not is_product_listed(driver, sku):
            print(f"SKU {sku} is not listed. Skipping.")
            return None  # Return None if product isn't listed.
        else:
            data = get_product_details(driver, sku)
    except Exception as e:
        print(f"Error processing SKU {sku}: {e}")
        data = None
    finally:
        driver.quit()
    return data

def main():
    input_file = "skus_iteminfo.txt"   # File containing the list of SKUs.
    output_file = "products_iteminfo.csv"
    
    # Read all SKUs from input file.
    with open(input_file, "r", encoding="utf-8") as f:
        skus = [line.strip() for line in f if line.strip()]
    
    with open(output_file, "w", newline='', encoding="utf-8") as csvfile:
        fieldnames = [
            "SKU", 
            "Product Name", 
            "Description", 
            "Specifications",
            "Main Image"
        ]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        
        max_workers = 9  # Set the number of workers.
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(process_sku, sku): sku for sku in skus}
            for future in as_completed(futures):
                sku = futures[future]
                try:
                    product_data = future.result()
                    if product_data is not None:
                        writer.writerow(product_data)
                        print(f"Data for SKU {sku} saved.")
                    else:
                        print(f"SKU {sku} skipped.")
                except Exception as e:
                    print(f"Error processing SKU {sku}: {e}")
    
    print(f"All data saved to {output_file}")

if __name__ == "__main__":
    main()
