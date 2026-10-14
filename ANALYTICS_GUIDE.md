# Analytics guide - in-app, Excel and Power BI

## 1. Analytics inside the app (admin) - live, nothing to set up
Open **Analytics** in the sidebar. It re-reads the data every 5 seconds, so a sale
made at the POS or an online order shows up by itself. Pick **Today / 7 days /
30 days / All time** and you get:

- Revenue, units sold, number of sales, average sale, POS vs online revenue
- **Most revenue by product** and **best sellers by units**
- **Where sales come from** - each Nigerian state (online orders) and "In-store" (POS)
- **Revenue over time** - by hour, day or month depending on the period

Cancelled orders are not counted. POS discounts are included, so revenue is what
was really paid.

## 2. Files the app keeps up to date for Excel / Power BI
After **every** sale, order, status change or product edit (about a second later),
the app rewrites these files in the `analytics_export` folder:

| File | What is in it |
|---|---|
| `sales_facts.csv` | One row per product sold - channel, date/time, product, units, revenue, location (state or In-store), salesperson, customer. **Use this one for most analysis.** |
| `products.csv` | Current stock levels and prices |
| `orders.csv` | Every online order with its status and warehouse |

Open the folder from **Analytics > Open export folder**. Turn this off or move the
folder in `config.py` (`AUTO_EXPORT`, `EXPORT_FOLDER`).

> Connect to the files through *Get Data* (below). Don't double-click a CSV to open it
> directly - Excel locks it and the app can't update it until you close it.

## 3. Excel (refreshes by itself while the workbook is open)
1. **Data > Get Data > From File > From Text/CSV** and choose `sales_facts.csv`, then **Load**.
2. Insert a **PivotTable** or chart from that table (e.g. Product on rows, Sum of revenue).
3. **Data > Queries & Connections**, right-click the query > **Properties**:
   tick **Refresh every [1] minutes** and **Refresh data when opening the file**.
4. Save the workbook. Optionally put its path in `config.py` as `EXCEL_WORKBOOK` to get
   an **Open Excel workbook** button on the Analytics page.

## 4. Power BI
1. **Power BI Desktop > Get data > Text/CSV** > `sales_facts.csv` > **Load**.
   The table will be called `sales_facts`.
2. Add these measures once (Modeling > New measure) and build your visuals on them:

```
Total Revenue = SUM(sales_facts[revenue])
Units Sold    = SUM(sales_facts[units])
Transactions  = COUNTROWS(SUMMARIZE(sales_facts, sales_facts[channel], sales_facts[reference]))
Average Sale  = DIVIDE([Total Revenue], [Transactions])
POS Revenue   = CALCULATE([Total Revenue], sales_facts[channel] = "POS (in-store)")
Online Revenue = CALCULATE([Total Revenue], sales_facts[channel] = "Online order")
```
3. Click **Refresh** whenever you want the newest data.

### What "real time" can and can't mean in Power BI
- The app's files are always current (within about a second). The limit is how often
  **Power BI re-reads them**.
- Power BI Desktop does not refresh itself when a file changes - you press Refresh.
- For automatic refresh, publish the report to the Power BI service. A file on your own
  computer needs an **on-premises data gateway**; scheduled refresh is limited to
  8 times a day on Pro and 48 on Premium Per User / Fabric.
- Pushing each sale straight into a Power BI dashboard (streaming / push datasets) is
  being retired by Microsoft - new ones can't normally be created - so it's not a good
  thing to build on. Microsoft points to Fabric Real-Time Intelligence instead.
- For second-by-second numbers, use the in-app Analytics page.

### Showing your Power BI report from the app
A Power BI report can't be embedded inside this desktop window. Put your report's link
in `config.py` (`POWERBI_REPORT_URL`) and an **Open Power BI report** button appears on
the Analytics page. Never use *Publish to web* for business data - it makes it public.

## 5. Connecting straight to the database (optional)
`test.db` has a ready-made view called `sales_facts` with the same columns as the CSV.
Power BI / Excel can read it through a SQLite **ODBC driver** (a free third-party install).
The CSV route above is simpler and needs nothing extra.

## Good to know
Everyone must use the **same** `test.db` for the numbers to match (one computer, or a
shared network folder). If your salespeople will work on several computers at once, the
app would need a shared database server - ask me and I can plan that next.
