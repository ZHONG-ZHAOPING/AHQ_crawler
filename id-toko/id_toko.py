ALL_EXPORT = False
DEALER_LINKS_FILENAME = "paramsetting.xlsx"
DEALER_PRODUCT_LIMIT = "?perpage=80"

## ===== Importing Libraries =====

import pandas as pd
import re
import time
import pyfiglet
import sys
import random
import os

os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2' 

from bs4 import BeautifulSoup
from datetime import datetime

CURRENT_DATE = datetime.now().date()
EXPORT_DATE = datetime.now().strftime("%Y%m%d")

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from concurrent.futures import ThreadPoolExecutor


## ===== Pre-scrape functions  =====

def timewait(priority= "low"):
    if priority == "low":
        time.sleep(random.randint(1, 2))
    elif priority == "medium":
        time.sleep(random.randint(2, 4))
    else:
        time.sleep(random.randint(4, 8))
    

def convert_numbers(str_number):
    cleaned_str = re.sub("[^\d\.]", "", str_number)
    if cleaned_str.count(".") > 1:
        parts = cleaned_str.split(".")
        integer_part = "".join(parts[:-1])
        decimal_part = parts[-1]
        cleaned_str = f"{integer_part}.{decimal_part}"

    return float(cleaned_str)

def loading_bar(counter, total, bar_length=50):
    percent = ("{0:.1f}").format(100 * (counter / float(total)))
    filled_length = int(bar_length * counter // total)
    bar = "█" * filled_length + "-" * (bar_length - filled_length)
    sys.stdout.write(f"\rProgress: |{bar}| {percent}% Complete ({counter}/{total})")
    sys.stdout.flush()

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

dealer_dictionary = get_dealer_links(DEALER_LINKS_FILENAME)

## ===== Scrapping helper functions =====

def find_brand(title, link, category):
    category_brand_map = {
    "LCD TV": ["AIWA", "AOC", "HISENSE", "LG", "PANASONIC", "PHILIPS", "SAMSUNG", "SHARP", "SONY", "TCL", "TOSHIBA", "XIAOMI"],

    "HAV": ["LG", "SAMSUNG", "SONY"],
    "MDR": ["AKG", "AUDIO TECHNICA", "ANKER", "CAYIN", "EDIFIER", "EGGEL", "HARMAN KARDON", "HUAWEI", "JABRA", "JBL", 
                    "LETSHUOER", "LOGITECH", "MARSHALL",
                  "MOONDROP", "MOREJOY", "MPOW", "NAKAMICHI", "NOTHING", "PHILIPS", "PIONEER", "POLYTRON", "RAZER", "SENNHEISER", 
                  "SHURE", "SONY", "SPINFIT", "STEELSERIES", "SUDIO",
                  "TANGZU WANER", "TAOTRONICS", "TRUTHEAR"],
    "PAS": ["SONY",],
    "ILC": ["SONY", "FUJIFILM", "CANON", "PANASONIC", "NIKON", "OM SYSTEM"],
    "LENS": ["SONY", "FUJIFILM", "CANON", "PANASONIC", "NIKON", "LEICA", "HASSELBLAD", "TAMRON", "LAOWA", "SIGMA", "SAMYANG", "VOIGTLANDER", "ZEISS", "HASSELBLAD", "OLYMPUS", "VILTROX"]
    }

    brand_list = category_brand_map[category]
   
    brand = None

    for b in brand_list:
        if b.lower() == "AUDIO TECHNICA":
            if "audio-technica" in title.lower() or "audio-technica" in link.lower():
                brand = b
                break
        elif b.lower() in title.lower() or b.lower() in link.lower():
            brand = b
            break

    return brand

def start_driver():
    options = webdriver.ChromeOptions()
    options.add_argument("--log-level=2")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.88 Safari/537.36")
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument("--disable-extensions")
    options.add_argument('--proxy-server="direct://"')
    options.add_argument("--proxy-bypass-list=*")
    options.add_argument("--ignore-certificate-errors")
    options.add_argument("--ignore-ssl-errors")
    options.add_argument("--disable-quic")
    options.add_argument('--no-sandbox')
    options.add_argument("--disable-webgl")
    options.add_argument("--allow-running-insecure-content")
    options.add_argument("--enable-unsafe-swiftshader")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)

    options.timeouts = { 'implicit': 500 }

    options.add_argument("--headless=new")
    options.add_argument("--window-position=-2400,-2400")

    options.headless = True
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    driver.set_page_load_timeout(5)
    driver.execute_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )

    return driver

DATA_COLUMNS = [
        "Date",
        "Dealer Site",
        "Category",
        "Material Description",
        "Brand",
        "Link",
        "Final Price",
        "Original Price",
        "Stock",
        "Average Rating",
        "Total Review",
        "Model Position",
    ]

def add_to_df(productDf, newEntry):
    return pd.concat([productDf, newEntry], ignore_index=True)

## ===== PHASE 1: Scrape Category Page =====
def scrape_cat_page(links_list):

    driver = start_driver()

    ## result dictionary: link -> html chunk
    result_dict = {}

    for link in links_list:
        print(link)
        page_counter = 0

        new_html_list = []

        while True:
            page_counter += 1
            while True:
                try:
                    driver.get(link + str(page_counter) + DEALER_PRODUCT_LIMIT)
                except TimeoutException:
                    continue
                break
            timewait("medium")

            errorCounter = 0
            html = driver.page_source

            while (
                "This site can't be reached" in html
                or "might be temporarily down or it may have moved permanently to a new web address"
                in html
                or not html
            ):
                if errorCounter >= 3:
                    print()
                    print("+--------------------------------+")
                    print(pyfiglet.figlet_format("ERROR"))
                    print(f"Could not access Page {page_counter}")
                    print("Please restart the script & retry!")
                    print("+--------------------------------+")
                    sys.exit()
                    break

                print(
                    f"  ERROR: Could not access Page {page_counter} -- Attempt {errorCounter + 1}, retrying..."
                )
                print()
                driver.quit()
                timewait("low")
                driver = start_driver()
                while True:
                    try:
                        driver.get(link + str(page_counter) + DEALER_PRODUCT_LIMIT)
                    except TimeoutException:
                        continue
                    break

                html = driver.page_source

                errorCounter += 1

            soup = BeautifulSoup(html, "html.parser")
            error_message, error_message2 = soup.find(
                "div", class_="css-3ytcpr-unf-emptystate e1mmy8p70"
            ), soup.find(
                "div", class_="css-e7ogvg-unf-emptystate e1mmy8p70"
            )

            if error_message or error_message2:
                # print("  ERROR FOUND: " + error_message.text)
                print("  Exiting page / category...\n")
                print()
                break
            
            ## check for promotions here
            promo_dict = {}
            counter = 1
            ## find promo container all

            # promo_dict[f"Promo Text {counter}"] = "promo_text"


            parsed_products = soup.find_all("div", class_="css-1sn1xa2")

            new_html_list += parsed_products
            print(f"  >> Page {page_counter} scraped!")

            timewait("low")

        if link not in result_dict:
            result_dict[link] = new_html_list
            ## result_dict[link][html] = new_html_list
            ## result_dict[link][promo] = promo_dict

    driver.quit()
    return result_dict

## ===== PHASE 2: Parse Material from HTML =====
def parse_cat_page(scraped_cat_page_result, dealer, category, export=False):

    parsed_columns = ["Category", "Material Description", "Dealer Site", "Link", "Model Position"]
    parsedDf = pd.DataFrame(columns=parsed_columns)

    ## dictionary for counting items in each link
    count_dict = {}

    for link, html_list in scraped_cat_page_result.items():

        if link not in count_dict:
            count_dict[link] = 0

        for pdt in html_list:

            ## ===== GETTING TITLE & LINK =====
            title_elm = pdt.find("div", class_="prd_link-product-name css-3um8ox")

            if not title_elm:
                continue

            title = title_elm.text.strip()

            count_dict[link] += 1
            model_position = count_dict[link]

            link_elm = pdt.find("a", class_="pcv3__info-content css-gwkf0u", href=True)[
                "href"
            ]

            newEntry = pd.DataFrame(
                [[category, title, dealer, link_elm, model_position]], columns=parsed_columns
            )
            parsedDf = pd.concat([parsedDf, newEntry], ignore_index=True)

    if export == True:
        if not os.path.exists(EXPORT_DATE):
            os.makedirs(EXPORT_DATE)
        FILENAME = f"{EXPORT_DATE}\scraped_{EXPORT_DATE}_ID_toko_{dealer.lower()}_{category.lower()}.xlsx"
        parsedDf.to_excel(FILENAME, index=False)

    return parsedDf

## ===== PHASE 3: Scrape Individual Product Pages =====

def scrape_page(soup, category, dealer, link, modelPosition, productDf):

    productDf = productDf
    ## MATERIAL DESCRIPTION - title
    title_elm = soup.find("div", class_="css-1nylpq2")
    if title_elm:
        title = title_elm.text.strip()
    else: 
        print(f"ERROR: Could not find title for {link}")

    ## edit the link
    if "?extParam" in link:
        link = link.split("?extParam")[0]

    ## BRAND
    brand = find_brand(title, link, category)

    price_elm = soup.find("div", class_="css-chstwd")
    original_price_elm = price_elm.find("div", class_="original-price")

    ## if only got original price => got two prices
    if original_price_elm:
        original_price = convert_numbers(original_price_elm.text.strip())
        final_price = convert_numbers(
            price_elm.find("div", class_="price").text.strip()
        )

    ## if got final price
    else:
        final_price = convert_numbers(
            price_elm.find("div", class_="price").text.strip()
        )
        original_price = final_price

    ## STOCK
    oos_elm = soup.find("span", string="Stok Habis")
    if oos_elm:
        stock = 0
    else:
        stock = 1

    ## REVIEW
    average_review_elm = soup.find(
        attrs={"data-testid": "lblPDPDetailProductRatingNumber"}
    )
    total_review_elm = soup.find(
        attrs={"data-testid": "lblPDPDetailProductRatingCounter"}
    )

    if average_review_elm or total_review_elm:
        average_review = convert_numbers(average_review_elm.text.strip())
        total_review = int(re.sub(r"\D", "", total_review_elm.text.strip()))
    else:
        average_review = None
        total_review = 0

    newEntry = pd.DataFrame(
                        [
                            [
                                CURRENT_DATE,
                                dealer,
                                category,
                                title,
                                brand,
                                link,
                                final_price,
                                original_price,
                                stock,
                                average_review,
                                total_review,
                                modelPosition,
                            ]
                        ],
                        columns=DATA_COLUMNS,
                    )
    productDf = add_to_df(productDf, newEntry)
    # productDf = pd.concat([productDf, newEntry], ignore_index=True)

    return productDf


def scrape_product_page(result1b, export=True):

    fullDf = pd.DataFrame(columns=DATA_COLUMNS)
    product_count = 0
    driver = start_driver()

    total_product = result1b.shape[0]
    for index, row in result1b.iterrows():

        modelPosition = row["Model Position"]
        link = row["Link"]
        category = row["Category"]
        title = row["Material Description"]
        dealer = row["Dealer Site"]

        while True:
            try:
                driver.get(link)
            except TimeoutException:
                continue
            break
        if random.randint(0, 100) > 99:
            timewait("high")
        else:
            timewait("low")

        errorCounter = 0
        html = driver.page_source
        soup = BeautifulSoup(html, "html.parser")
        title_elm = soup.find("div", class_="css-1nylpq2")

        while (
            "This site can't be reached" in html
            or "might be temporarily down or it may have moved permanently to a new web address"
            in html
            or not html
            or not title_elm
        ):
            if errorCounter >= 3:
                print()
                print("+--------------------------------+")
                print(pyfiglet.figlet_format("ERROR"))
                print(f"Could not access Page for {title}")
                print("Please restart the script & retry!")
                print("+--------------------------------+")
                sys.exit()
                break

            driver.quit()
            timewait("low")
            driver = start_driver()
            while True:
                try:
                    driver.get(link)
                except TimeoutException:
                    continue
                break
            html = driver.page_source
            soup = BeautifulSoup(html, "html.parser")
            title_elm = soup.find("div", class_="css-1nylpq2")
            errorCounter += 1

        soup = BeautifulSoup(html, "html.parser")

        buttons = None
        buttons2 = None

        try:
            divs = driver.find_elements(By.CLASS_NAME, "css-hayuji")
            if divs:
                buttons = divs[0].find_elements(By.TAG_NAME, "button")
            if len(divs) > 1:
                buttons2 = divs[1].find_elements(By.TAG_NAME, "button")

        except NoSuchElementException:
            pass

        if buttons:
            ## iterate through variants
            for button in buttons:
                button.click()
                time.sleep(random.randint(0,1))

                if buttons2:
                    for button2 in buttons2:
                        button2.click()
                        time.sleep(random.randint(0,1))
                        link = driver.current_url
                        soup = BeautifulSoup(driver.page_source, "html.parser")
                        fullDf = scrape_page(soup, category, dealer, link, modelPosition, fullDf)
                        product_count += 1

                else:
                    link = driver.current_url
                    soup = BeautifulSoup(driver.page_source, "html.parser")
                    fullDf = scrape_page(soup, category, dealer, link, modelPosition, fullDf)
                    product_count += 1

        else:
            time.sleep(random.randint(0,1))
            link = driver.current_url
            fullDf = scrape_page(soup, category, dealer, link, modelPosition, fullDf)
            product_count += 1

        loading_bar(index + 1, total_product)

    driver.quit()
    if export == True:
        if not os.path.exists(EXPORT_DATE):
            os.makedirs(EXPORT_DATE)
        FILENAME = f"{EXPORT_DATE}\{EXPORT_DATE}_ID_toko_{dealer.lower()}_{category.lower()}.xlsx"
        fullDf.to_excel(FILENAME, index=False)

    print()
    print("Total Products: " + str(product_count))
    return fullDf


def crawl_toko(dealer_dictionary = dealer_dictionary):

    for dealer, catergories in dealer_dictionary.items():
        for category, links_list in catergories.items():
            
            if os.path.exists(f"{EXPORT_DATE}\{EXPORT_DATE}_ID_toko_{dealer.lower()}_{category.lower()}.xlsx"):
                continue
            else:
                ## scraping of cat page
                print(f"SCRAPPING {dealer.upper()} - {category.upper()}...")
                scrape_cat_page_result = scrape_cat_page(links_list)
                parse_cat_page_result = parse_cat_page(scrape_cat_page_result, dealer, category, export=ALL_EXPORT)

                ## scraping of product page
                print(f"ITERATING INDIV PRODUCT PAGE FOR {dealer.upper()} - {category.upper()}...")
                scrape_product_page_result = scrape_product_page(parse_cat_page_result, export=True)

    return  


## ===== (NEW) PHASE 3: Scrape Individual Product Pages with Playwright =====



def merge_all_files():

    fullDf = pd.DataFrame(columns=DATA_COLUMNS)

    for dealer, catergories in dealer_dictionary.items():
        for category, links_list in catergories.items():
            if os.path.exists(f"{EXPORT_DATE}\{EXPORT_DATE}_ID_toko_{dealer.lower()}_{category.lower()}.xlsx"):
                df = pd.read_excel(f"{EXPORT_DATE}\{EXPORT_DATE}_ID_toko_{dealer.lower()}_{category.lower()}.xlsx")
                fullDf = pd.concat([fullDf, df], ignore_index=True)

    FILENAME = f"{EXPORT_DATE}\{EXPORT_DATE}_ID_toko_FULL.xlsx"
    fullDf.to_excel(FILENAME, index=False)

    return fullDf

def validate_masterlist():
    try:
        masterlist = pd.read_excel("toko_masterlist.xlsx")
        today = pd.read_excel(f"{EXPORT_DATE}\{EXPORT_DATE}_ID_toko_FULL.xlsx")
    except FileNotFoundError:
        print("Masterlist or today's file not found!")
        return
    
    def is_partial_match(link, masterlist_links):
        return any(masterlink in link or link in masterlink for masterlink in masterlist_links)

    today['Dealer and Material'] = today['Dealer Site'] + " - " + today['Material Description']
    masterlist['Dealer and Material'] = masterlist['Dealer Site'] + " - " + masterlist['Material Description']
     
    new_df = today[~today['Dealer and Material'].apply(lambda link: is_partial_match(link, masterlist['Dealer and Material'].values))]
    missing_df = masterlist[~masterlist['Dealer and Material'].apply(lambda link: is_partial_match(link, today['Dealer and Material'].values))]

    new_df = new_df.drop(columns=['Dealer and Material'])
    missing_df = missing_df.drop(columns=['Dealer and Material'])
    new_df.to_excel(f"{EXPORT_DATE}\{EXPORT_DATE}_ID_toko_NEW.xlsx", index=False)
    missing_df.to_excel(f"{EXPORT_DATE}\{EXPORT_DATE}_ID_toko_MISSING.xlsx", index=False)

    ## update masterlist with new data and updated last seen
    masterlist_updated = masterlist.copy()
    matching_links = masterlist['Dealer and Material'].isin(today['Dealer and Material'])
    masterlist_updated.loc[matching_links, 'Last Seen'] = today['Date'].iloc[0]  

    new_rows_in_today = today[~today['Dealer and Material'].isin(masterlist['Dealer and Material'])]
    new_rows_in_today = new_rows_in_today.rename(columns={'Date': 'Last Seen'})
    updated_masterlist = pd.concat([masterlist_updated, new_rows_in_today], ignore_index=True)
    updated_masterlist = updated_masterlist.drop(columns=['Dealer and Material'])
    updated_masterlist.to_excel("toko_masterlist.xlsx", index=False)

    return

crawl_toko()
# with ThreadPoolExecutor(max_workers=4) as executor:
#     executor.map(crawl_toko)

merge_all_files()
validate_masterlist()



#### below is wip ======

class Promotion:
    def __init__(self, type, amount, percent, minimum):
        self.type = type
        self.type = amount
        self.percent = percent
        self.minimum = minimum

    ## ===== basic functions =====
    def get_type(self):
        return self.type
    
    def get_amount(self):
        return self.amount
    
    def get_percent(self):
        return self.percent
    
    def get_minimum(self):
        return self.minimum
    
    ## ===== application of promo ====
    def apply_promo(self, price):
        if (self.type == "Cashback" or self.type == "Diskon") and price > self.minimum:
            if self.amount:
                price -= self.amount
            elif self.percent:
                price -= price * self.percent
        return price

def testetst():

    driver = start_driver()
    driver.get("https://www.tokopedia.com/jbl-official/etalase/true-wireless")
    # driver.get("https://www.tokopedia.com/jpckemang/etalase/canon-lens/page/1")
    driver.refresh()
    time.sleep(10)


    html = driver.page_source
    soup = BeautifulSoup(html, "html.parser")
    promo_containers = soup.find("div", class_="css-azhcs7 e18kalgp2")
    if promo_containers:
        parent_promos = promo_containers.find_all("div", recursive=False)[1]
        print(f"number of promos: {len(parent_promos)}")

        for promo in parent_promos:
            # print(">>>>>>  PROMO  <<<<<<")
            promo_text = promo.find("div", class_= "css-1o4foo6")
            print(promo_text.text)

            ## type of promo
            if re.search(r'cashback', promo_text.text, re.IGNORECASE):
                promo_type = "Cashback"
            elif re.search(r'diskon', promo_text.text, re.IGNORECASE):
                promo_type = "Diskon"
            elif re.search(r'gratis ongkir', promo_text.text, re.IGNORECASE):
                promo_type = "Gratis Ongkir"
            else:
                promo_type = "Unknown"
            print(promo_type)

            ## promo amount
            amount_match = re.search(r'(\d+%|\d+[a-zA-Z]+)\s*(?=min)', promo_text.text)
            print(f"Amount: {amount_match.group(1)}")

            ## promo condition
            min_purchase_match = re.search(r'min\. Pembelian (\d+[a-zA-Z]+)', promo_text.text)
            print(f"Minimum: {min_purchase_match.group(1)}")
            print()

            ## store the promotion into dictionary

## apply promo
def apply_promo(price):
    return

# testetst()