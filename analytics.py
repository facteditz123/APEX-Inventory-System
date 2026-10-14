import csv
import os
import subprocess
import sys
import tkinter as tk
import webbrowser
from collections import defaultdict
from datetime import date, datetime, timedelta

import config
from charts import HBarChart, VBarChart
from ui import C, FONT, FlatButton, Card, Segmented, money, page_header, stat_cards

FACT_COLS = ["channel", "sold_at", "sale_date", "reference", "product_id", "product",
             "units", "revenue", "location", "salesperson", "customer"]
PERIODS = ["Today", "7 days", "30 days", "All time"]
REFRESH_MS = 5000


#  export
def _write_csv(path, header, rows):
    tmp = path + ".tmp"
    with open(tmp, "w", newline="", encoding="utf-8-sig") as f:     
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    os.replace(tmp, path)                 


def export_all(db, folder):
    """Rewrite the CSV files that Excel / Power BI read. Returns the list of files written."""
    os.makedirs(folder, exist_ok=True)
    jobs = {
        "sales_facts.csv": (FACT_COLS, [tuple(r) for r in db.sales_facts()]),
        "products.csv": (["product_id", "product", "price", "quantity"], db.products()),
        "orders.csv": (["order_id", "created", "updated", "status", "customer", "state",
                        "warehouse", "items", "total"],
                       [(o["id"], o["created"], o["updated"], o["status"], o["customer"], o["state"],
                         o["wh_name"], o["items"], o["total"]) for o in db.orders()]),
    }
    done = []
    for name, (header, rows) in jobs.items():
        try:
            _write_csv(os.path.join(folder, name), header, rows)
            done.append(name)
        except PermissionError:            
            pass
    return done


def open_path(target):
    if os.name == "nt":
        os.startfile(target)              
    elif sys.platform == "darwin":
        subprocess.Popen(["open", target])
    else:
        subprocess.Popen(["xdg-open", target])


#  analysis
def top_n(rows, key, value, n=5):
    totals = defaultdict(float)
    for r in rows:
        totals[r[key]] += r[value]
    return sorted(totals.items(), key=lambda kv: kv[1], reverse=True)[:n]


def trend(rows, period, since):
    """Chronological [(label, revenue)]: hourly for Today, daily up to ~6 weeks, else monthly."""
    if not rows:
        return []
    if period == "Today":
        by = defaultdict(float)
        for r in rows:
            by[int(r["sold_at"][11:13])] += r["revenue"]
        return [(f"{h:02d}h", by.get(h, 0)) for h in range(min(by), max(by) + 1)]
    by = defaultdict(float)
    for r in rows:
        by[r["sale_date"]] += r["revenue"]
    first = date.fromisoformat(since) if since else date.fromisoformat(min(by))
    if (date.today() - first).days > 45:
        months = defaultdict(float)
        for d, v in by.items():
            months[d[:7]] += v
        return sorted(months.items())
    days = [first + timedelta(i) for i in range((date.today() - first).days + 1)]
    return [(d.strftime("%m-%d"), by.get(d.isoformat(), 0)) for d in days]


#  Analytics page
class AnalyticsPage(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=C["bg"])
        self.app, self.period, self.job = app, "30 days", None
        money0 = lambda v: f"{config.CURRENCY}{v:,.0f}"
        units = lambda v: f"{int(v):,} sold"

        top = tk.Frame(self, bg=C["bg"])
        top.pack(fill="x", pady=(0, 8))
        head = page_header(top, "Analytics", "")
        head.pack(side="left")
        self.subtitle = head.winfo_children()[1]
        btns = tk.Frame(top, bg=C["bg"])
        btns.pack(side="right")
        self.msg = tk.Label(btns, font=(FONT, 9), bg=C["bg"], fg=C["muted"])
        self.msg.pack(side="bottom", anchor="e")
        row = tk.Frame(btns, bg=C["bg"])
        row.pack(side="top")
        for text, cmd in (("Export now", self.export_now), ("Open export folder", self.open_folder)):
            self.small_button(row, text, cmd)
        if config.POWERBI_REPORT_URL:
            self.small_button(row, "Open Power BI report", lambda: webbrowser.open(config.POWERBI_REPORT_URL))
        if config.EXCEL_WORKBOOK:
            self.small_button(row, "Open Excel workbook", lambda: self.safe_open(config.EXCEL_WORKBOOK))

        bar = tk.Frame(self, bg=C["bg"])
        bar.pack(fill="x", pady=(0, 10))
        Segmented(bar, PERIODS, command=self.set_period, value=self.period).pack(side="left")
        self.live = tk.Label(bar, font=(FONT, 9, "bold"), bg=C["bg"], fg=C["success"])
        self.live.pack(side="right")

        f, self.k = stat_cards(self, [
            ("rev", "Revenue", C["accent"]), ("units", "Units sold", C["success"]),
            ("tx", "Transactions", "#0891b2"), ("avg", "Average sale", "#7c3aed"),
            ("pos", "In-store (POS)", "#0d9488"), ("web", "Online orders", "#ea580c")])
        f.pack(fill="x")

        grid = tk.Frame(self, bg=C["bg"])
        grid.pack(fill="both", expand=True, pady=(12, 0))
        grid.columnconfigure((0, 1), weight=1, uniform="g")
        grid.rowconfigure((0, 1), weight=1, uniform="g")
        self.c_rev = self.chart_card(grid, 0, 0, "Most revenue by product", HBarChart, C["accent"], money0)
        self.c_units = self.chart_card(grid, 0, 1, "Best sellers (units sold)", HBarChart, C["success"], units)
        self.c_loc = self.chart_card(grid, 1, 0, "Where sales come from", HBarChart, "#ea580c", money0)
        self.c_trend = self.chart_card(grid, 1, 1, "Revenue over time", VBarChart, "#0d9488", money0)
        self.bind("<Destroy>", self.on_destroy)

    # building helpers
    @staticmethod
    def small_button(parent, text, cmd):
        FlatButton(parent, text, cmd, bg=C["card"], fg=C["text"], hover=C["border"], pady=6,
                   highlightthickness=1, highlightbackground=C["border"]).pack(side="left", padx=(8, 0))

    @staticmethod
    def chart_card(grid, r, c, title, chart_class, colour, fmt):
        card = Card(grid)
        card.grid(row=r, column=c, sticky="nsew", padx=(0 if c == 0 else 6, 6 if c == 0 else 0),
                  pady=(0 if r == 0 else 6, 6 if r == 0 else 0))
        tk.Label(card, text=title, font=(FONT, 11, "bold"), bg=C["card"], fg=C["text"]
                 ).pack(anchor="w", padx=14, pady=(10, 2))
        chart = chart_class(card, colour, fmt)
        chart.pack(fill="both", expand=True, padx=14, pady=(0, 10))
        return chart

    # live refresh
    def on_destroy(self, e):
        if e.widget is self:
            self.cancel()

    def cancel(self):
        if self.job:
            try:
                self.after_cancel(self.job)
            except tk.TclError:
                pass
            self.job = None

    def tick(self):
        self.job = None
        if self.winfo_exists() and self.winfo_ismapped():
            self.refresh()

    def set_period(self, value):
        self.period = value
        self.refresh()

    def since(self):
        today = date.today()
        start = {"Today": today, "7 days": today - timedelta(days=6),
                 "30 days": today - timedelta(days=29)}.get(self.period)
        return start.isoformat() if start else None

    def refresh(self):
        self.cancel()
        since = self.since()
        rows = self.app.db.sales_facts(since)
        revenue = sum(r["revenue"] for r in rows)
        units = sum(r["units"] for r in rows)
        tx = len({(r["channel"], r["reference"]) for r in rows})
        pos = sum(r["revenue"] for r in rows if r["channel"].startswith("POS"))
        self.k["rev"].config(text=money(revenue))
        self.k["units"].config(text=f"{units:,}")
        self.k["tx"].config(text=f"{tx:,}")
        self.k["avg"].config(text=money(revenue / tx if tx else 0))
        self.k["pos"].config(text=money(pos))
        self.k["web"].config(text=money(revenue - pos))

        by_rev = top_n(rows, "product", "revenue")
        by_units = top_n(rows, "product", "units")
        by_loc = top_n(rows, "location", "revenue")
        self.c_rev.set_data(by_rev)
        self.c_units.set_data(by_units)
        self.c_loc.set_data(by_loc)
        self.c_trend.set_data(trend(rows, self.period, since))
        if rows:
            self.subtitle.config(text=f"Top earner: {by_rev[0][0]}   •   Best seller: "
                                      f"{by_units[0][0]}   •   Most sales from: {by_loc[0][0]}")
        else:
            self.subtitle.config(text="No sales in this period yet - they will appear here the moment they happen")
        self.live.config(text=f"●  Live  ·  updated {datetime.now():%H:%M:%S}")
        self.job = self.after(REFRESH_MS, self.tick)

    # export actions
    def export_now(self):
        done = export_all(self.app.db, config.EXPORT_FOLDER)
        self.msg.config(text=f"Exported {len(done)} files" if done else "Files are open elsewhere - try again",
                        fg=C["success"] if done else C["danger"])

    def safe_open(self, target):
        try:
            open_path(target)
        except OSError as e:
            self.msg.config(text=f"Couldn't open: {e}", fg=C["danger"])

    def open_folder(self):
        export_all(self.app.db, config.EXPORT_FOLDER)
        self.safe_open(config.EXPORT_FOLDER)
