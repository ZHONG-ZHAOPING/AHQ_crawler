from datetime import datetime

current_date = datetime.now().strftime("%Y%m%d")

import sg_courts_scrape as scrape
import sg_courts_parse as parse

courts_html_list = scrape.scrape()
courts_df = parse.parse(courts_html_list)

FILENAME = f"{current_date}_SG_courts.xlsx"
courts_df.to_excel(FILENAME, index=False)