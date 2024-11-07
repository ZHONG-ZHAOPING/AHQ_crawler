## ===== Import libraries =====
from bs4 import BeautifulSoup

import pandas as pd

import time
from datetime import datetime
current_date = datetime.now().date()

import re

## ===== Importing Setup =====
import setup

setup.setup()

## ===== Parsing the HTML =====
def parse(html_list):

    courts_product_dict = {}

    for pair in html_list:
        product_list = pair[0]
        category = pair[1]

        for pdt in product_list:

        
            ## ===== GETTING TITLE & LINK=====
            title_elm = pdt.find("h3", class_="product name product-item-name")

            if not title_elm:
                continue

            if category not in courts_product_dict:
                courts_product_dict[category] = 1
            else:
                courts_product_dict[category] += 1

            title = title_elm.text.strip()
            # print(title)

            link_elm = pdt.find("a", class_ = "product-item-link", href=True)['href']

            ## ===== GETTING BRAND =====
            if category == "LCD TV":
                brand_list = setup.tv_brands
            elif category == "Audio":
                brand_list = setup.audio_brands
            elif category == "MDR":
                brand_list = setup.headphone_brands
                
            brand = None

            for b in brand_list:
                if b.lower() == "AUDIO TECHNICA":
                    if "audio-technica" in title.lower() or "audio-technica" in link_elm.lower():
                        brand = b
                        break
                elif b.lower() in title.lower() or b.lower() in link_elm.lower():
                    brand = b
                    break

            ## ===== GETTING STOCK =====
            error_message = pdt.find("div", class_="stock unavailable")

            if error_message:
                stock = False
                # print("NO STOCK")
            else:
                stock = True
            
            ## ===== GETTING PRICE =====
            price_box_elm = pdt.find("div", class_="price-box price-final_price")
            special_price_elm = price_box_elm.find("span", class_ = "special-price")

            if special_price_elm:
                special_price = special_price_elm.find("span", class_ = "price").text.strip()
                # print("special price: " + str(special_price))

                original_price = price_box_elm.find("span", class_ = "old-price").find("span", class_ = "price").text.strip()
                # print("original price: " + str(original_price))

                newEntry = pd.DataFrame([
                    [brand, title, category, "SGD", setup.convert_numbers(special_price), setup.convert_numbers(original_price), 
                        stock, current_date, "COURTS", link_elm, courts_product_dict[category]]
                ], columns = setup.columns)
                
            else:
                only_one_price = price_box_elm.find("span", class_ = "price").text.strip()
                # print("=> ONLY ONE price: " + str(only_one_price))
                newEntry = pd.DataFrame([
                    [brand, title, category, "SGD", setup.convert_numbers(only_one_price), setup.convert_numbers(only_one_price), 
                        stock, current_date, "COURTS", link_elm, courts_product_dict[category]]
                ], columns = setup.columns)

            setup.productDf = setup.add_to_df(setup.productDf, newEntry)

    return setup.productDf