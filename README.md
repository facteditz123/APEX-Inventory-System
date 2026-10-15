# Stock Management System

Inventory, point of sale and nationwide order tracking in one desktop app
(Python + Tkinter + SQLite - nothing extra to install).

## Run
    python mainapp.py
Linux may need: `sudo apt install python3-tk`

## First time
1. Click **Sign up**, choose **Admin**, and enter the admin access code
   (default `ADMIN02`).
2. Create salesperson accounts with the staff code (default `STAFF02`).
3. Customers sign up on their own - no code needed.

**Change both codes in `config.py` before you share the app.**
Your existing products in `test.db` are kept.

## Who can do what
| | Admin | Salesperson | Customer |
|---|:--:|:--:|:--:|
| Dashboard (each role has its own) | yes | yes | yes |
| Inventory - add / edit / delete products | yes | - | - |
| **Analytics** - live sales analysis + Excel/Power BI feed | yes | - | - |
| Products - check what is available (read-only) | yes | yes | - |
| Point of Sale (billing + checkout) | - | yes | - |
| Sales history | all sales | own sales | - |
| Shipping & Orders (track + update status) | yes | yes | - |
| Warehouses (edit address / phone) | yes | - | - |
| Users | yes | - | - |
| Shop + place orders, My Orders | - | - | yes |

## Shipping & orders
- A customer picks items, chooses their state, and the app lists the 3 nearest
  warehouses (straight-line distance). They collect from the one they choose.
- Every order moves: **In Warehouse -> In Transit -> Delivered** (or Cancelled,
  which returns the items to stock). Each step is logged with who did it and when.
- **Filter by location** on the Shipping & Orders page shows the status of
  orders and products at any single warehouse; combine it with the status tabs.
- There is one warehouse per state + FCT (37). Rename them and add real
  addresses and phone numbers on the Warehouses page.

## Analytics, Excel and Power BI
Admins get a live **Analytics** page (top products, revenue, where sales come from,
revenue over time). The app also keeps CSV files in `analytics_export/` up to date
after every sale so Excel / Power BI can read them. Full steps, ready-made Power BI
measures and the limits of "real time" are in **ANALYTICS_GUIDE.md**.

## Settings (`config.py`)
Currency symbol, low-stock level, the two access codes, whether salespeople can
see everyone's sales, and the Excel / Power BI export folder and shortcuts.

## Files
`mainapp.py` (start here) - `auth.py` login/sign-up - `dashboards.py` -
`staff_pages.py` inventory, POS, sales, users, warehouses - `orders.py` shipping,
shop, my orders - `analytics.py` + `charts.py` live analytics and CSV export -
`database.py` - `ui.py` - `config.py`
