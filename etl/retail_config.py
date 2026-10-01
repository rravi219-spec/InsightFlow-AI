from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/raw/online_retail_II.xlsx"
DATABASE = ROOT / "data/processed/online_retail.sqlite3"
REPORT = ROOT / "data/processed/retail_quality.json"
PROFILE = ROOT / "data/processed/retail_raw_profile.json"
SOURCE_URL = "https://archive.ics.uci.edu/static/public/502/online+retail+ii.zip"
SHEETS = ("Year 2009-2010", "Year 2010-2011")
COLUMNS = ("Invoice", "StockCode", "Description", "Quantity", "InvoiceDate",
           "Price", "Customer ID", "Country")
