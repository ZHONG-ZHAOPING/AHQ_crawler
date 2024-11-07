## ===== Importing Libraries =====

from selenium import webdriver 
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.chrome.options import Options

from bs4 import BeautifulSoup
import time
import pyfiglet

import io
import sys

## ===== Pre-scrape initialisations =====
courts_links = [
    ["https://www.courts.com.sg/tv-entertainment/vision/television?p=", "LCD TV"],
    ["https://www.courts.com.sg/tv-entertainment/audio?p=", "Audio"],
    ["https://www.courts.com.sg/computing-mobile/earphones-headphones?p=", "MDR"]
]

COURTS_PRODUCT_LIMIT = "&product_list_limit=32"

## ===== Scrapping the website =====
def scrape():
    options = webdriver.ChromeOptions() 
    options.add_argument('--disable-extensions')
    options.add_argument('--proxy-server="direct://"')
    options.add_argument('--proxy-bypass-list=*')
    # options.add_argument("--headless=new/")
    driver = webdriver.Chrome(options=options) 
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})") 

    courts_html_list = []
    courts_print_report = []

    for x in courts_links:
        link = x[0]
        category = x[1]

        counter = 0

        while True:
            counter += 1
            driver.get(link + str(counter) + COURTS_PRODUCT_LIMIT)
            time.sleep(5)

            ## check if there are items
            html = driver.page_source
            soup = BeautifulSoup(html, 'html.parser')

            error_message = soup.find("div", class_="message info empty")
            
            if error_message:
                print("  ERROR FOUND: " + error_message.text)
                print("  Exiting category...\n")
                break
            
            parsed_products = soup.find_all("li", class_ = "item product product-item")

            courts_html_list += [
                [parsed_products, category]
            ]
            print(f">> {category} Page {counter} parsed!")
        
        courts_print_report += [
            [category, counter]
        ]

    driver.quit()

    page_counter = 0
    print()
    print("+--------------------------------+")
    print(pyfiglet.figlet_format("Courts SG"))
    for x in courts_print_report:
        print(f"{x[0]}: {x[1] - 1} pages parsed")
        page_counter += x[1] - 1

    print()
    print(f"==> TOTAL pages parsed: {page_counter}")
    print("+--------------------------------+")


    return courts_html_list