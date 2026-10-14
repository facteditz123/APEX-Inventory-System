import tkinter as tk

from config import LOW_STOCK_LEVEL
from ui import (C, FONT, ROLE_COLOUR, STATUS_STYLE, Card, banner, greeting, make_tree, money,
                stat_cards)


def table_card(parent, title, columns, widths, anchors=None, height=5):
    card = Card(parent)
    tk.Label(card, text=title, font=(FONT, 12, "bold"), bg=C["card"], fg=C["text"]
             ).pack(anchor="w", padx=14, pady=(12, 6))
    f, tree = make_tree(card, columns, widths, anchors, height=height)
    f.pack(fill="both", expand=True, padx=14, pady=(0, 14))
    return card, tree


def two_columns(parent):
    lower = tk.Frame(parent, bg=C["bg"])
    lower.columnconfigure(0, weight=1, uniform="l")
    lower.columnconfigure(1, weight=1, uniform="l")
    lower.rowconfigure(0, weight=1)
    return lower


def fill_low_stock(tree, db):
    tree.delete(*tree.get_children())
    for pid, name, _, qty in sorted((p for p in db.products() if p[3] <= LOW_STOCK_LEVEL),
                                    key=lambda p: p[3]):
        tree.insert("", "end", values=(pid, name, qty), tags=("out" if qty <= 0 else "low",))


def fill_sales(tree, rows, with_cashier):
    tree.delete(*tree.get_children())
    for n, s in enumerate(rows):
        vals = (s["id"], s["created"][5:16]) + ((s["cashier"] or "-",) if with_cashier else ()) \
            + (money(s["total"]),)
        tree.insert("", "end", values=vals, tags=("odd",) if n % 2 else ())


class AdminDashboard(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=C["bg"])
        self.app = app
        banner(self, ROLE_COLOUR["admin"], f"{greeting()}, {app.user['full_name'].split()[0]}",
               "Admin overview - stock, sales, warehouses and orders at a glance",
               ("Manage inventory", lambda: app.show("Inventory"))).pack(fill="x")
        f, self.s1 = stat_cards(self, [
            ("products", "Products", C["accent"]), ("units", "Units in stock", C["success"]),
            ("value", "Stock value", "#0891b2"), ("alerts", "Low / out of stock", C["warn"]),
            ("today", "POS sales today", "#7c3aed")])
        f.pack(fill="x", pady=(14, 0))
        f, self.s2 = stat_cards(self, [
            ("wh", "Orders in warehouse", "#d97706"), ("tr", "Orders in transit", "#2563eb"),
            ("dl", "Orders delivered", C["success"]), ("users", "Registered users", "#64748b"),
            ("whs", "Warehouses", "#0d9488")])
        f.pack(fill="x", pady=(10, 0))
        lower = two_columns(self)
        lower.pack(fill="both", expand=True, pady=(14, 0))
        c, self.low = table_card(lower, "Needs restocking",
                                 [("id", "ID"), ("name", "Product"), ("qty", "Qty")],
                                 [90, 170, 60], {"qty": "e"})
        c.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        c, self.sales = table_card(lower, "Recent POS sales",
                                   [("id", "#"), ("d", "Date"), ("by", "Cashier"), ("t", "Total")],
                                   [50, 110, 120, 90], {"t": "e"})
        c.grid(row=0, column=1, sticky="nsew", padx=(8, 0))

    def refresh(self):
        db = self.app.db
        items = db.products()
        oc = db.order_counts()
        self.s1["products"].config(text=f"{len(items):,}")
        self.s1["units"].config(text=f"{sum(i[3] for i in items):,}")
        self.s1["value"].config(text=money(sum(i[2] * i[3] for i in items)))
        low = sum(1 for i in items if i[3] <= LOW_STOCK_LEVEL)
        self.s1["alerts"].config(text=str(low), fg=C["danger"] if low else C["text"])
        self.s1["today"].config(text=money(db.sales_stats()["today_total"]))
        self.s2["wh"].config(text=str(oc["In Warehouse"]))
        self.s2["tr"].config(text=str(oc["In Transit"]))
        self.s2["dl"].config(text=str(oc["Delivered"]))
        self.s2["users"].config(text=str(len(db.users())))
        self.s2["whs"].config(text=str(len(db.warehouses())))
        fill_low_stock(self.low, db)
        fill_sales(self.sales, db.recent_sales(8), True)


class SalesDashboard(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=C["bg"])
        self.app = app
        banner(self, ROLE_COLOUR["salesperson"],
               f"{greeting()}, {app.user['full_name'].split()[0]}",
               "Sales workspace - ring up sales and keep orders moving",
               ("Open Point of Sale", lambda: app.show("Point of Sale"))).pack(fill="x")
        f, self.s = stat_cards(self, [
            ("today", "My sales today", "#0d9488"), ("n", "My transactions today", "#0891b2"),
            ("all", "My total sales", "#7c3aed"), ("prod", "Products available", C["accent"]),
            ("ship", "Orders awaiting dispatch", "#d97706")])
        f.pack(fill="x", pady=(14, 0))
        lower = two_columns(self)
        lower.pack(fill="both", expand=True, pady=(14, 0))
        c, self.sales = table_card(lower, "My recent sales",
                                   [("id", "#"), ("d", "Date"), ("t", "Total")],
                                   [60, 150, 100], {"t": "e"}, height=8)
        c.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        c, self.low = table_card(lower, "Running low - tell the customer or restock",
                                 [("id", "ID"), ("name", "Product"), ("qty", "Qty")],
                                 [90, 170, 60], {"qty": "e"}, height=8)
        c.grid(row=0, column=1, sticky="nsew", padx=(8, 0))

    def refresh(self):
        db, uid = self.app.db, self.app.user["id"]
        st = db.sales_stats(uid)
        self.s["today"].config(text=money(st["today_total"]))
        self.s["n"].config(text=str(st["today_n"]))
        self.s["all"].config(text=money(st["all_total"]))
        self.s["prod"].config(text=str(sum(1 for p in db.products() if p[3] > 0)))
        self.s["ship"].config(text=str(db.order_counts()["In Warehouse"]))
        fill_sales(self.sales, db.recent_sales(8, cashier_id=uid), False)
        fill_low_stock(self.low, db)


class CustomerDashboard(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=C["bg"])
        self.app = app
        banner(self, ROLE_COLOUR["customer"],
               f"{greeting()}, {app.user['full_name'].split()[0]}",
               "Order what you need and pick it up at the warehouse closest to you",
               ("Shop now", lambda: app.show("Shop"))).pack(fill="x")
        f, self.s = stat_cards(self, [
            ("wh", "Ready in warehouse", "#d97706"), ("tr", "In transit", "#2563eb"),
            ("dl", "Delivered", C["success"]), ("spent", "Total spent", "#7c3aed")])
        f.pack(fill="x", pady=(14, 0))
        lower = tk.Frame(self, bg=C["bg"])
        lower.pack(fill="both", expand=True, pady=(14, 0))
        lower.columnconfigure(0, weight=3)
        lower.columnconfigure(1, weight=2)
        lower.rowconfigure(0, weight=1)
        c, self.orders = table_card(
            lower, "My recent orders",
            [("id", "Order #"), ("items", "Items"), ("st", "Status"), ("t", "Total")],
            [60, 190, 90, 90], {"t": "e"}, height=8)
        c.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self.orders.bind("<Double-1>", lambda e: app.show("My Orders"))

        near = Card(lower)
        near.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        tk.Label(near, text="Your nearest pick-up point", font=(FONT, 12, "bold"), bg=C["card"],
                 fg=C["text"]).pack(anchor="w", padx=16, pady=(12, 6))
        self.near_title = tk.Label(near, font=(FONT, 15, "bold"), bg=C["card"], fg=ROLE_COLOUR["customer"],
                                   wraplength=300, justify="left")
        self.near_title.pack(anchor="w", padx=16)
        self.near_info = tk.Label(near, font=(FONT, 10), bg=C["card"], fg=C["muted"],
                                  wraplength=300, justify="left")
        self.near_info.pack(anchor="w", padx=16, pady=(6, 0))

    def refresh(self):
        db, u = self.app.db, self.app.user
        oc = db.order_counts(user_id=u["id"])
        orders = db.orders(user_id=u["id"])
        self.s["wh"].config(text=str(oc["In Warehouse"]))
        self.s["tr"].config(text=str(oc["In Transit"]))
        self.s["dl"].config(text=str(oc["Delivered"]))
        self.s["spent"].config(text=money(sum(o["total"] for o in orders if o["status"] != "Cancelled")))
        self.orders.delete(*self.orders.get_children())
        for o in orders[:8]:
            self.orders.insert("", "end", iid=str(o["id"]), tags=(STATUS_STYLE[o["status"]][0],),
                               values=(f"#{o['id']}", o["items"], o["status"], money(o["total"])))
        if u.get("state"):
            w, km = db.nearest_warehouses(u["state"], 1)[0]
            self.near_title.config(text=w["name"])
            self.near_info.config(text=f"{w['address']}\n{w['phone'] or 'Phone not listed yet'}\n\n"
                                       f"Based on your saved location: {u['state']}"
                                       + (f" ({km:.0f} km away)" if km else ""))
        else:
            self.near_title.config(text="Location not set")
            self.near_info.config(text="Choose your state when you place an order and we'll show "
                                       "the closest warehouse.")
