import os
import sys

APP_TITLE = "APEX INVENTORY SYSTEM"

if getattr(sys, "frozen", False):
    APP_FOLDER = os.path.dirname(sys.executable)
else:
    APP_FOLDER = os.path.dirname(os.path.abspath(__file__))

DB_FILE = os.path.join(APP_FOLDER, "test.db")

CURRENCY = "₦"
LOW_STOCK_LEVEL = 5

ADMIN_CODE = "ADMIN02"
STAFF_CODE = "STAFF02"

SALESPERSON_SEES_ALL_SALES = False

AUTO_EXPORT = True
EXPORT_FOLDER = os.path.join(APP_FOLDER, "analytics_export")

# Power BI report and Excel workbook
POWERBI_REPORT_URL = ""
EXCEL_WORKBOOK = os.path.join(APP_FOLDER, "Inventory.xlsx")