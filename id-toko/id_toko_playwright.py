import pandas as pd
import re
import time
import pyfiglet
import sys
import random
import os
from datetime import datetime

import asyncio
from playwright.async_api import async_playwright

EXPORT_DATE = datetime.now().strftime("%Y%m%d")

def loading_bar(counter, total, bar_length=50):
    percent = ("{0:.1f}").format(100 * (counter / float(total)))
    filled_length = int(bar_length * counter // total)
    bar = "█" * filled_length + "-" * (bar_length - filled_length)
    sys.stdout.write(f"\rProgress: |{bar}| {percent}% Complete ({counter}/{total})")
    sys.stdout.flush()

def convert_numbers(str_number):
    cleaned_str = re.sub("[^\d]", "", str_number)
    
    # Return the number as a float or int depending on the input
    return float(cleaned_str) if cleaned_str else 0

def find_brand(title, link):
    brand = None

    if "audio-technica" in title.lower() or "audio-technica" in link.lower() or\
        "audio technica" in title.lower() or "audio technica" in link.lower():
        brand = "AUDIO TECHNICA"

    if brand is None:
        brand = title.split(" ")[0].upper()

    return brand

def apply_best_promotion(promotions, final_price):
    """Finds and applies the best promotion (diskon or cashback) and adjusts the final price."""
    
    def convert_promo_value(promo_text):
        """Converts promo text like '50 rb' or '1jt' into numbers."""
        promo_text = promo_text.replace(" ", "").lower()
        if 'rb' in promo_text:
            return float(promo_text.replace('rb', '')) * 1000
        elif 'jt' in promo_text:
            return float(promo_text.replace('jt', '')) * 1000000
        elif '%' in promo_text:
            return float(promo_text.replace('%', ''))
        return float(promo_text)

    best_promotion_value = 0
    best_promotion_type = None
    
    for promo in promotions:
        # Extract promotion type (diskon/cashback) and values
        match = re.search(r"(diskon|cashback)\s+([\d%]+)\s+min\.\s+([\d\w]+)", promo.lower())
        
        if match:
            promo_type = match.group(1)  # diskon or cashback
            promo_value = convert_promo_value(match.group(2))  # promotion value
            min_requirement = convert_promo_value(match.group(3))  # minimum price required
            
            # Check if the final price meets the minimum requirement
            if final_price >= min_requirement:
                if promo_type == 'diskon':
                    # Diskon is a flat discount
                    promo_amount = promo_value
                elif promo_type == 'cashback':
                    # Cashback is a percentage of the final price
                    promo_amount = (promo_value / 100) * final_price
                
                # Find the best (highest) promotion value
                if promo_amount > best_promotion_value:
                    best_promotion_value = promo_amount
                    best_promotion_type = promo_type

    # Deduct the best promotion from the final price
    if best_promotion_value > 0:
        final_price -= best_promotion_value

    return final_price

def get_dealer_links(filename = "paramsetting.xlsx", sheet_name = "Dictionary"):
    df = pd.read_excel(filename, sheet_name = sheet_name)

    dealer_dictionary = {}

    for index, row in df.iterrows():
        dealer = row["Dealer"]
        category = row["Category"]
        link = row["Link"]

        if dealer not in dealer_dictionary:
            dealer_dictionary[dealer] = {category: [link]}
        else:
            if category not in dealer_dictionary[dealer]:
                dealer_dictionary[dealer][category] = [link]
            else:
                dealer_dictionary[dealer][category].append(link)

    return dealer_dictionary

DEALER_LINKS_FILENAME = "paramsetting.xlsx"
dealer_dictionary = get_dealer_links(DEALER_LINKS_FILENAME)

MAX_CONCURRENT_TASKS = 5  # Control concurrency

async def scroll_page(page):
    """Scroll down the page to load dynamically loaded content."""
    previous_height = await page.evaluate("document.body.scrollHeight")
    while True:
        # Scroll down to the bottom of the page
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await page.wait_for_timeout(2000)  # Wait for new content to load
        
        # Check if the page height has changed (new content loaded)
        current_height = await page.evaluate("document.body.scrollHeight")
        if current_height == previous_height:
            break  # Stop when no new content is loaded
        previous_height = current_height

# ### ===== PHASE 1: SCRAPING CATEGORIES =====

async def scrape_category(semaphore, browser, links, const, dealer, category):
    """To call and concurrently run all category pages for a dealer"""

    tasks = []
    for link in links:
        tasks.append(scrape_link_with_pagination(semaphore, browser, link, const, dealer, category))
    
    # Gather results from all links
    results = await asyncio.gather(*tasks)
    
    # Flatten the list of results and ensure it's a list of dictionaries
    flattened_results = [item for sublist in results for item in sublist]
    
    return flattened_results

async def scrape_link_with_pagination(semaphore, browser, base_url, const, dealer, category):
    """To iterate through all pages of a category"""
    async with semaphore:
        counter = 1
        all_product_data = []
        position = 1

        while True:
            url = f"{base_url}{counter}{const}"
            page = await browser.new_page()
            success, product_data, position = await scrape_category_page(page, url, position, dealer, category)

            if not success:
                await page.close()
                break

            all_product_data.extend(product_data)
            counter += 1
            await page.close()

        return all_product_data
    
async def scrape_category_page(page, url, position_start, dealer, category):
    """Scrapes a category page, retrieves divs, product details, and universal promotions, and tracks position."""
    await page.goto(url, timeout=50000, wait_until="domcontentloaded")  # Increased timeout and changed wait condition

    # Scroll to load all dynamic content
    await page.reload()
    await scroll_page(page)

    # Check for error state divs
    empty_state_1 = await page.query_selector('div.css-3ytcpr-unf-emptystate.e1mmy8p70')
    empty_state_2 = await page.query_selector('div.css-e7ogvg-unf-emptystate.e1mmy8p70')

    if empty_state_1 or empty_state_2:
        return False, [], position_start  # Skip this page if empty state is found

    # Collect all divs with the target class for products
    divs = await page.query_selector_all('div.css-1sn1xa2')

    # Calculate the total number of products as position_out_of
    position_out_of = position_start + len(divs) - 1

    # Check for the presence of the promo container (optional)
    promo_container = await page.query_selector('div.css-azhcs7.e18kalgp2')
    promotions = []
    if promo_container:
        # Get promotions from the container
        promo_divs = await promo_container.query_selector_all('div.css-1o4foo6')
        for promo in promo_divs:
            promo_text = await promo.inner_text()
            promo_text = promo_text.replace("\n", " ").replace("Pembelian", "").strip()
            promotions.append(promo_text)

    # Extract title, link, and position from each div
    product_data = []
    position = position_start
    for div in divs:
        title_div = await div.query_selector('div.prd_link-product-name.css-3um8ox')
        link_anchor = await div.query_selector('a.pcv3__info-content.css-gwkf0u')

        # Ensure both title and link exist
        if title_div and link_anchor:
            title = await title_div.inner_text()
            link = await link_anchor.get_attribute('href')
            
            # Trim ?extParam from the link if it exists
            if "?extParam" in link:
                link = link.split("?extParam")[0]

            # Store all product data, including the universal promotions, dealer, and category
            product_data.append({
                'Dealer': dealer,
                'Category': category,
                'Position': position,
                'Position Out Of': position_out_of,  # New field added here
                'Title': title.replace("|", "-"),  # Replaced with Material Description
                'Link': link,
                'Promotions': promotions  # Same promotions for all products on the page
            })
            position += 1  # Increment position for each div
    
    return True, product_data, position  # Return the updated position


# ### ===== PHASE 2 =====


# ### ===== FINAL STEPS =====



# ## year|"month"|"sales_org"|"language"|"main category"|"product group"|"model_id"|"brand"|"original material description"|"material description"|"sku"|"ean"|"url"|"iskit"|"seller"|"date"|"price"|"currency"|"stock"|"position"|"position_out_of"|"review_num"|"review_avg"|"screen size"|"technology"|"quality"|"size segment"|"size segment (gfk)"|"misc_1"|"misc_2"|"misc_3"|"misc_4"|"misc_5"|"promotion_text_1"|"promotion_text_1_en"|"promotion_text_10"|"promotion_text_10_en"|"promotion_text_11"|"promotion_text_11_en"|"promotion_text_12"|"promotion_text_12_en"|"promotion_text_13"|"promotion_text_13_en"|"promotion_text_14"|"promotion_text_14_en"|"promotion_text_15"|"promotion_text_15_en"|"promotion_text_16"|"promotion_text_16_en"|"promotion_text_17"|"promotion_text_17_en"|"promotion_text_18"|"promotion_text_18_en"|"promotion_text_19"|"promotion_text_19_en"|"promotion_text_2"|"promotion_text_2_en"|"promotion_text_3"|"promotion_text_3_en"|"promotion_text_4"|"promotion_text_4_en"|"promotion_text_5"|"promotion_text_5_en"|"promotion_text_6"|"promotion_text_6_en"|"promotion_text_7"|"promotion_text_7_en"|"promotion_text_8"|"promotion_text_8_en"|"promotion_text_9"|"promotion_text_9_en"|"promotion_text_line"|"promotion_text_line_en"|"trade in scheme"|"trade in scheme_en"|"misc_10"|"misc_11"|"misc_12"|"misc_13"|"misc_14"|"misc_15"|"misc_16"|"misc_17"|"misc_18"|"misc_19"|"misc_20"|"misc_6"|"misc_7"|"misc_8"|"misc_9"|"discount%"|"discount_amount"|"old_price"|"marketingdatacreatedon"|"createdon"



async def scrape_product_details(page, dealer, category, position, position_out_of, promotions, data_store):
    """Scrapes product details like title, prices, stock, reviews, applies promotions, stores results, and adds created_on."""
    
    # Get the current datetime in the format "YYYY-MM-DD HH:MM:SS"
    created_on = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Scraping title
    title_element = await page.query_selector('div.css-1nylpq2')
    title = (await title_element.inner_text()).strip() if title_element else "N/A"

    # Scraping URL and handling extParam
    link = page.url
    if "?extParam" in link:
        link = link.split("?extParam")[0]

    # Scraping prices
    price_elm = await page.query_selector('div.css-chstwd')
    if price_elm:
        original_price_elm = await price_elm.query_selector('div.original-price')
        if original_price_elm:
            original_price_text = await original_price_elm.inner_text()
            original_price = convert_numbers(original_price_text.strip())

            final_price_elm = await price_elm.query_selector('div.price')
            final_price_text = await final_price_elm.inner_text()
            final_price = convert_numbers(final_price_text.strip())
        else:
            final_price_elm = await price_elm.query_selector('div.price')
            final_price_text = await final_price_elm.inner_text()
            final_price = convert_numbers(final_price_text.strip())
            original_price = final_price
    else:
        original_price, final_price = None, None

    # Apply best promotion and adjust final price
    final_price = apply_best_promotion(promotions, final_price)

    # Scraping stock
    oos_elm = await page.query_selector('span:text("Stok Habis")')
    stock = 0 if oos_elm else 1

    # Scraping reviews
    average_review_elm = await page.query_selector('[data-testid="lblPDPDetailProductRatingNumber"]')
    total_review_elm = await page.query_selector('[data-testid="lblPDPDetailProductRatingCounter"]')

    if average_review_elm or total_review_elm:
        average_review = convert_numbers((await average_review_elm.inner_text()).strip()) if average_review_elm else None
        total_review = int(re.sub(r"\D", "", (await total_review_elm.inner_text()).strip())) if total_review_elm else 0
    else:
        average_review, total_review = None, 0

    # Store data in the shared list, including the created_on field
    data_store.append({
        'Dealer': dealer,
        'Category': category,
        'Position': position,
        'Position Out Of': position_out_of,  # New field added here
        'Brand': find_brand(title, link),
        'Material Description': title.replace("|", "-"),
        'Link': link,
        'Promotions': promotions,
        'Original Price': original_price,
        'Final Price': final_price,
        'Stock': stock,
        'Average Review': average_review,
        'Total Review': total_review,
        'Created On': created_on  # Add the created_on timestamp
    })


async def scrape_variant_combinations(page, dealer, category, position, position_out_of, promotions, data_store):
    """Handles variant selection and calls scrape_product_details to store the results."""
    
    variant_sets = await page.query_selector_all('div.css-hayuji')

    # If no variant buttons are found, scrape the product details directly
    if not variant_sets:
        await scrape_product_details(page, dealer, category, position, position_out_of, promotions, data_store)
        return

    # Handle cases with variant buttons
    buttons_1 = await variant_sets[0].query_selector_all('button') if len(variant_sets) >= 1 else []
    buttons_2 = await variant_sets[1].query_selector_all('button') if len(variant_sets) >= 2 else []

    for btn1 in buttons_1 or [None]:
        if btn1:
            await btn1.click()
            await page.wait_for_timeout(1000)
        for btn2 in buttons_2 or [None]:
            if btn2:
                await btn2.click()
                await page.wait_for_timeout(1000)

            # Scrape product details after selecting variants
            await scrape_product_details(page, dealer, category, position, position_out_of, promotions, data_store)




async def process_product(result, browser, semaphore, data_store, counter, total, failed_links):
    """Processes a single product: access the link, scrape variants, and handle errors."""
    dealer = result['Dealer']
    category = result['Category']
    position = result['Position']
    position_out_of = result['Position Out Of']  # New field
    link = result['Link']
    promotions = result['Promotions']

    async with semaphore:
        page = await browser.new_page()

        errorCounter = 0
        while True:
            try:
                await page.goto(link)
                await page.reload()
                await page.wait_for_timeout(2000)

                # Pass data_store to store results, including position_out_of
                await scrape_variant_combinations(page, dealer, category, position, position_out_of, promotions, data_store)
                break

            except Exception as e:
                errorCounter += 1

            if errorCounter >= 3:
                failed_links.append(result)
                break
        
        # Update the progress bar
        counter[0] += 1
        loading_bar(counter[0], total)
        
        await page.close()





async def process_dealer_results_concurrently(dealer_results, browser, semaphore, data_store):
    """Processes dealer results concurrently, with retry logic for failed links up to 3 times."""
    total = len(dealer_results)
    counter = [0]  # List used to keep counter mutable
    failed_links = []  # List to track failed links
    failedCounts = 0  # Counter for the number of retries

    # Process the first round of links
    tasks = [process_product(result, browser, semaphore, data_store, counter, total, failed_links) for result in dealer_results]
    await asyncio.gather(*tasks)

    # Retry failed links if there are any, up to 3 times
    while failed_links and failedCounts < 3:
        total = len(failed_links)  # Reset total for retry
        counter = [0]  # Reset counter for retry
        retry_tasks = [process_product(result, browser, semaphore, data_store, counter, total, []) for result in failed_links]
        
        # Reset failed_links for this retry attempt
        failed_links = []
        
        await asyncio.gather(*retry_tasks)

        failedCounts += 1

    # If after 3 retries some links still fail, log them to a file
    if failedCounts >= 3 and failed_links:
        print("Failed 3 times, moving on")
        with open(f"{EXPORT_DATE}/failed_links.txt", "a") as f:
            for link in failed_links:
                f.write(f"{link['Link']} - Failed after 3 retries\n")


## old export

# async def export_to_excel(dealer, data):
#     """Exports the scraped data into an Excel file organized by dealer."""
#     df = pd.DataFrame(data)

#     if not os.path.exists(EXPORT_DATE):
#         os.makedirs(EXPORT_DATE)
#     FILENAME = f"{EXPORT_DATE}\{EXPORT_DATE}_ID_toko_{dealer.lower()}.xlsx"
#     df.to_excel(FILENAME, index=False)


## new export

async def export_to_excel(dealer, data):
    df = pd.DataFrame(data)

    if not os.path.exists(EXPORT_DATE):
        os.makedirs(EXPORT_DATE)
    FILENAME = f"{EXPORT_DATE}\{EXPORT_DATE}_ID_toko_{dealer.lower()}.csv"

    MAX_PROMOTIONS = 20
    for i in range(1, MAX_PROMOTIONS + 1):
        column_name = f"promotion_text_{i}"
        df[column_name] = df["Promotions"].apply(lambda x: x[i - 1] if i - 1 < len(x) else "")
    
    # Drop the original "Promotions" column after splitting
    df = df.drop(columns=["Promotions"])
    
    column_mapping = {
        "Dealer": "seller",
        "Category": "main category",
        "Position": "position",
        "Position Out Of": "position_out_of",
        "Brand": "brand",
        "Material Description": "material description",
        "Link": "url",
        # "Promotions": "promotion_text_1",
        "Original Price": "old_price",
        "Final Price": "price",
        "Stock": "stock",
        "Average Review": "review_avg",
        "Total Review": "review_num",
        "Created On": "createdon"
    }

    # Rename columns
    df = df.rename(columns=column_mapping)

    # Define all required columns, filling missing ones with blanks
    columns = [
        "year", "month", "sales_org", "language", "main category", "product group", "model_id", "brand",
        "original material description", "material description", "sku", "ean", "url", "iskit", "seller", "date",
        "price", "currency", "stock", "position", "position_out_of", "review_num", "review_avg", "screen size",
        "technology", "quality", "size segment", "size segment (gfk)", "misc_1", "misc_2", "misc_3", "misc_4",
        "misc_5", "promotion_text_1", "promotion_text_1_en", "promotion_text_10", "promotion_text_10_en",
        "promotion_text_11", "promotion_text_11_en", "promotion_text_12", "promotion_text_12_en", "promotion_text_13",
        "promotion_text_13_en", "promotion_text_14", "promotion_text_14_en", "promotion_text_15", "promotion_text_15_en",
        "promotion_text_16", "promotion_text_16_en", "promotion_text_17", "promotion_text_17_en", "promotion_text_18",
        "promotion_text_18_en", "promotion_text_19", "promotion_text_19_en", "promotion_text_2", "promotion_text_2_en",
        "promotion_text_3", "promotion_text_3_en", "promotion_text_4", "promotion_text_4_en", "promotion_text_5",
        "promotion_text_5_en", "promotion_text_6", "promotion_text_6_en", "promotion_text_7", "promotion_text_7_en",
        "promotion_text_8", "promotion_text_8_en", "promotion_text_9", "promotion_text_9_en", "promotion_text_line",
        "promotion_text_line_en", "trade in scheme", "trade in scheme_en", "misc_10", "misc_11", "misc_12", "misc_13",
        "misc_14", "misc_15", "misc_16", "misc_17", "misc_18", "misc_19", "misc_20", "misc_6", "misc_7", "misc_8",
        "misc_9", "discount%", "discount_amount", "old_price", "marketingdatacreatedon", "createdon"
    ]

    # Add any missing columns as blanks
    for col in columns:
        if col not in df.columns:
            df[col] = ""

    # Reorder DataFrame columns and save as .xlsb with '|' delimiter
    df = df[columns]
    df.to_csv(FILENAME, sep="|", index=False, encoding="utf-8", header=True, quotechar='"', quoting=1)

# Example usage:
# export_to_xlsb(df, "/mnt/data/output_file.xlsb")


async def scrape_dealer(dealer, dealer_dict):
    """Scrapes all categories and links for a dealer, stores data, and exports it to Excel."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, args=[
            "--window-position=-2400,-2400",
            "--start-maximized",
            "--disable-http2",
            "--disable-webgl",
            "--disable-blink-features=AutomationControlled"
        ])
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_TASKS)
        const = "?perpage=80"

        # Initialize dealer-specific results and data store
        dealer_results = []
        data_store = []  # This will store the results for each dealer

        # Scrape each category for the current dealer
        for category, links in dealer_dict.items():
            category_results = await scrape_category(semaphore, browser, links, const, dealer, category)
            dealer_results.extend(category_results)  # Collect all category results for the dealer

        # After scraping category pages, process product details concurrently
        await process_dealer_results_concurrently(dealer_results, browser, semaphore, data_store)

        # After scraping, export the results to an Excel file (one file per dealer)
        await export_to_excel(dealer, data_store)

        await browser.close()
        return dealer_results


async def main():

    for dealer, categories in dealer_dictionary.items():

        if os.path.exists(f"{EXPORT_DATE}\{EXPORT_DATE}_ID_toko_{dealer.lower()}.csv"):
            print(f"{dealer.lower()} found!")
            continue  

        print(f"\n ==> Starting to scrape dealer: {dealer}")
        dealer_results = await scrape_dealer(dealer, categories)


if __name__ == "__main__":
    asyncio.run(main())