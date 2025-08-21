import csv
import time
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from concurrent.futures import ThreadPoolExecutor, as_completed

def check_listed(driver, sku):
    url = f"https://www.iteminfo.com/product/{sku}"
    driver.get(url)
    try:
        WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.CSS_SELECTOR, "#wrapper > div > div.container > div > div.col-xs-12.col-sm-12.col-md-9.col-lg-9.details-page > div > div.col-lg-7.col-md-7.col-sm-6.col-xs-12.wow.fadeInUp.product-section > div.hidden-xs > h1 > span")))
        return True
    except Exception:
        return False

def scrape_product(driver, sku):
    url = f"https://www.iteminfo.com/product/{sku}"
    driver.get(url)
    wait = WebDriverWait(driver, 10)
    time.sleep(1)
    product_name, description, specifications, main_image, details_sections = "", "", "", "", {}
    try:
        product_name_elem = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#wrapper > div > div.container > div > div.col-xs-12.col-sm-12.col-md-9.col-lg-9.details-page > div > div.col-lg-7.col-md-7.col-sm-6.col-xs-12.wow.fadeInUp.product-section > div.hidden-xs > h1 > span")))
        product_name = product_name_elem.text.strip()
    except Exception as e:
        print(f"Error getting product name for SKU {sku}: {e}")
    try:
        image_elem = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "a.main-product-images img.img-responsive.lazyOwl")))
        main_image = image_elem.get_attribute("src") or ""
        if main_image.startswith("//"): main_image = "https:" + main_image
    except Exception as e:
        print(f"Error getting main product image for SKU {sku}: {e}")
    try:
        description_container = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, ".product-description")))
        description_elem = description_container.find_element(By.CSS_SELECTOR, "span.ng-binding")
        description = description_elem.text.strip() if description_elem else "No description available."
        bullet_points = []
        try:
            bullet_elements = description_container.find_elements(By.CSS_SELECTOR, "ul.ng-binding li")
            bullet_points = [f"- {b.text.strip()}" for b in bullet_elements]
        except Exception:
            pass
        if bullet_points: description += "\n" + "\n".join(bullet_points)
    except Exception as e:
        print(f"Error getting description for SKU {sku}: {e}")
    try:
        details_elem = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div#details")))
        details_html = details_elem.get_attribute("outerHTML")
        soup = BeautifulSoup(details_html, "html.parser")
        sections = []
        headers = soup.select("a.accordionHead")
        for header in headers:
            section_title = header.get_text(strip=True)
            content_div = header.find_next_sibling("div", class_="accordion-body")
            section_content = ""
            if content_div:
                rows = content_div.select("table tbody tr")
                row_texts = []
                for row in rows:
                    cells = row.find_all("td")
                    if len(cells) >= 2:
                        label = cells[0].get_text(strip=True); value = cells[1].get_text(strip=True)
                        row_texts.append(f"- {label}: {value}")
                    else:
                        row_texts.append(f"- {row.get_text(strip=True)}")
                section_content = "\n".join(row_texts)
            sections.append(f"{section_title}:\n{section_content}")
            details_sections[section_title] = section_content
        specifications = "\n\n".join(sections)
    except Exception as e:
        print(f"Error getting specifications for SKU {sku}: {e}")
    result = {"SKU": sku, "Product Name": product_name, "Main Image": main_image, "Description": description, "Specifications": specifications}
    result.update(details_sections)
    return result

def launch_driver():
    opts = Options(); opts.add_argument("--headless"); opts.add_argument("--disable-gpu")
    return webdriver.Chrome(options=opts)

def handle_sku(sku):
    driver = launch_driver()
    try:
        if not check_listed(driver, sku):
            print(f"SKU {sku} is not listed. Skipping."); return None
        return scrape_product(driver, sku)
    except Exception as e:
        print(f"Error processing SKU {sku}: {e}"); return None
    finally:
        driver.quit()

def main():
    input_file, output_file = "skus_iteminfo.txt", "products_iteminfo.csv"
    with open(input_file, "r", encoding="utf-8") as f: skus = [l.strip() for l in f if l.strip()]
    results = []
    with ThreadPoolExecutor(max_workers=10) as ex:
        futures = {ex.submit(handle_sku, sku): sku for sku in skus}
        for fut in as_completed(futures):
            sku = futures[fut]
            try:
                data = fut.result()
                if data is not None:
                    results.append(data); print(f"Data for SKU {sku} saved.")
                else:
                    print(f"SKU {sku} skipped.")
            except Exception as e:
                print(f"Error processing SKU {sku}: {e}")
    base_fields = ["SKU", "Product Name", "Main Image", "Description", "Specifications"]
    extra_fields = sorted({k for r in results for k in r.keys() if k not in base_fields})
    fieldnames = base_fields + extra_fields
    with open(output_file, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        for row in results: writer.writerow(row)
    print(f"All data saved to {output_file}")

if __name__ == "__main__":
    main()
