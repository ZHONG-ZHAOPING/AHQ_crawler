## ===== Importing the required libraries ===== 

import pandas as pd
import re

import time
from datetime import datetime
current_date = datetime.now().date()


## ===== Pre-scrape functions  ===== 

def convert_numbers(str):
    return re.sub("[^\d\.]", "", str)


## ===== Initialising brand names ===== 

def initialise_brands():
    global tv_brands, audio_brands, headphone_brands
    tv_brands = ["AIWA", "AOC", "HISENSE", "LG", "PHILIPS", "SAMSUNG", "SHARP", "SONY", "TCL", "XIAOMI"]

    audio_brands = ["AIWA", "APPLE", "AUDIO TECHNICA", "CREATIVE", "DENON", "HARMAN KARDON", "HISENSE", "HONEYWELL", "JBL", "LG", "MARSHALL",
                    "MICROSOFT", "MUZEN", "PHILIPS", "SAMSUNG", "SHARP", "SONOS", "SONY", "TRIBIT", "ULTIMATE EARS", "YAMAHA"]

    headphone_brands = ["APPLE", "AUDIO TECHNICA", "BEATS", "BELKIN", "BOWERS & WILKINS", "CMF", "CREATIVE", "DEFUNC", "HAPPY PLUGS", "HONEYWELL",
                        "IFLYTEK", "JABRA", "JBL", "KLIPSCH", "LOGITECH", "MARSHALL", "NOTHING", "OPPO", "PHILIPS", "SAMSUNG", "SARAMONIC",
                        "SHOKZ", "SKULLCANDY", "SONOS", "SONY", "SOUL", "SUDIO", "TOZO", "TRIBIT"]


## ===== Initialising the dataframes ===== 

def initialise_df():
    global columns, productDf
    columns = ["Brand", "Description", "Category", "Currency", "Current Price (LCY)", "Original Price (LCY)", "Stock", "Date", "Dealer Site", "Link", "Model Position"]
    productDf = pd.DataFrame(columns = columns)

def add_to_df(productDf, newEntry):
    return pd.concat([productDf, newEntry], ignore_index=True)

def setup():
    initialise_brands()
    initialise_df()