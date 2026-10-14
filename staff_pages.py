import csv
import os
import tkinter as tk
from datetime import datetime
from tkinter import filedialog, messagebox, ttk

import config
from ui import (C, FONT, Card, FlatButton, center_window, labeled_entry,
                make_tree, money, page_header, to_float, to_int)
from config import APP_TITLE, CURRENCY, LOW_STOCK_LEVEL


#  Inventory
class InventoryPage(tk.Frame):
    """Admin: full management.  Salesperson (readonly=True): just check availability."""
    COLS = [("id", "Product ID"), ("name", "Name"), ("price", "Price"),
            ("qty", "Quantity"), ("status", "Status")]

    def __init__(self, parent, app, readonly=False):
        super().__init__(parent, bg=C["bg"])
        self.app, self.readonly = app, readonly
        self.selected_id, self.sort_col, self.sort_rev = None, "id", False
        self.v_id, self.v_name = tk.StringVar(), tk.StringVar()
        self.v_price, self.v_qty, self.v_search = tk.StringVar(), tk.StringVar(), tk.StringVar()
        self.v_search.trace_add("write", lambda *_: self.refresh())
        self.msg = None

        top = tk.Frame(self, bg=C["bg"])
        top.pack(fill="x", pady=(0, 14))
        page_header(top, "Products" if readonly else "Inventory",
                    "Check what is available and the current prices" if readonly
                    else "Add, edit and track your products").pack(side="left")
        if not readonly:
            FlatButton(top, "+  New product", self.open_add_dialog, bg=C["success"],
                       hover=C["success_dark"]).pack(side="right")
        FlatButton(top, "Export CSV", self.export_csv, bg=C["card"], fg=C["text"],
                   hover=C["border"], highlightthickness=1, highlightbackground=C["border"]
                   ).pack(side="right", padx=(0, 10))

        body = tk.Frame(self, bg=C["bg"])
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=1)
        body.rowconfigure(0, weight=1)
        table_card = Card(body)
        table_card.grid(row=0, column=0, sticky="nsew", padx=(0, 0 if readonly else 14))
        bar = tk.Frame(table_card, bg=C["card"])
        bar.pack(fill="x", padx=14, pady=(14, 8))
        tk.Label(bar, text="Search", font=(FONT, 9, "bold"), bg=C["card"], fg=C["muted"]
                 ).pack(side="left")
        self.search_entry = ttk.Entry(bar, textvariable=self.v_search, style="Modern.TEntry")
        self.search_entry.pack(side="left", fill="x", expand=True, padx=(8, 0))
        self.count_lbl = tk.Label(bar, font=(FONT, 9), bg=C["card"], fg=C["muted"])
        self.count_lbl.pack(side="right", padx=(10, 0))
        f, self.tree = make_tree(table_card, self.COLS, [90, 170, 90, 70, 70],
                                 {"price": "e", "qty": "e", "status": "center"}, height=16)
        f.pack(fill="both", expand=True, padx=14, pady=(0, 14))
        for cid, head in self.COLS:
            self.tree.heading(cid, text=head, command=lambda c=cid: self.sort_by(c),
                              anchor={"price": "e", "qty": "e", "status": "center"}.get(cid, "w"))
        self.tree.bind("<<TreeviewSelect>>", self.on_select)
        self.bind_all("<Control-f>", self.focus_search)
        if not readonly:
            self.build_form(body)

    def build_form(self, body):
        form = Card(body)
        form.grid(row=0, column=1, sticky="ns")
        inner = tk.Frame(form, bg=C["card"])
        inner.pack(padx=18, pady=16)
        inner.columnconfigure(0, weight=1)
        self.form_title = tk.Label(inner, font=(FONT, 13, "bold"), bg=C["card"], fg=C["text"])
        self.form_title.grid(row=0, column=0, sticky="w")
        self.e_id = labeled_entry(inner, "PRODUCT ID", self.v_id, 1, 26)
        self.e_name = labeled_entry(inner, "PRODUCT NAME", self.v_name, 2, 26)
        labeled_entry(inner, f"SELL PRICE ({CURRENCY.strip()})", self.v_price, 3, 26)
        labeled_entry(inner, "QUANTITY", self.v_qty, 4, 26)
        self.add_btn = FlatButton(inner, "Add product", self.add)
        self.upd_btn = FlatButton(inner, "Save changes", self.update, bg=C["success"],
                                  hover=C["success_dark"])
        self.del_btn = FlatButton(inner, "Delete", self.delete, bg=C["danger"],
                                  hover=C["danger_dark"])
        FlatButton(inner, "Clear form", self.clear, bg=C["bg"], fg=C["text"], hover=C["border"]
                   ).grid(row=23, column=0, sticky="ew")
        self.msg = tk.Label(inner, font=(FONT, 9), bg=C["card"], fg=C["muted"], wraplength=210,
                            justify="left")
        self.msg.grid(row=24, column=0, sticky="w", pady=(12, 0))
        for e in (self.e_id, self.e_name):
            e.bind("<Return>", lambda ev: (self.update if self.selected_id is not None else self.add)())
        self.set_mode(False)

    def focus_search(self, _e=None):
        try:
            self.search_entry.focus_set()
        except tk.TclError:
            pass

    def set_mode(self, editing):
        self.form_title.config(text="Edit product" if editing else "New product")
        for b in (self.add_btn, self.upd_btn, self.del_btn):
            b.grid_remove()
        if editing:
            self.upd_btn.grid(row=20, column=0, sticky="ew", pady=(20, 6))
            self.del_btn.grid(row=21, column=0, sticky="ew", pady=(0, 6))
        else:
            self.add_btn.grid(row=20, column=0, sticky="ew", pady=(20, 6))

    def say(self, text, ok=True):
        if self.msg:
            self.msg.config(text=text, fg=C["success"] if ok else C["danger"])

    def can_edit(self):
        return self.app.user["role"] == "admin"        

    @staticmethod
    def parse_product(pid, name, price, qty):
        pid, name, qty = pid.strip(), name.strip(), qty.strip()
        if not pid or not name:
            return None, "Product ID and name are required."
        price = to_float(price, None)
        if price is None or price < 0:
            return None, "Enter a valid price (0 or more)."
        if not qty.isdigit():
            return None, "Quantity must be a whole number (0 or more)."
        return (pid, name, price, int(qty)), None

    def read_form(self):
        data, err = self.parse_product(self.v_id.get(), self.v_name.get(),
                                       self.v_price.get(), self.v_qty.get())
        if err:
            self.say(err, False)
        return data

    def open_add_dialog(self):
        if not self.can_edit():
            return
        win = tk.Toplevel(self)
        win.title("New product")
        win.configure(bg=C["card"])
        win.resizable(False, False)
        win.transient(self.winfo_toplevel())
        inner = tk.Frame(win, bg=C["card"])
        inner.pack(padx=24, pady=20)
        inner.columnconfigure(0, weight=1)
        tk.Label(inner, text="Add a new product", font=(FONT, 14, "bold"), bg=C["card"],
                 fg=C["text"]).grid(row=0, column=0, sticky="w")
        v = {k: tk.StringVar() for k in ("id", "name", "price", "qty")}
        v["qty"].set("0")
        first = labeled_entry(inner, "PRODUCT ID", v["id"], 1, 34)
        labeled_entry(inner, "PRODUCT NAME", v["name"], 2, 34)
        labeled_entry(inner, f"SELL PRICE ({CURRENCY.strip()})", v["price"], 3, 34)
        labeled_entry(inner, "STARTING QUANTITY", v["qty"], 4, 34)
        err = tk.Label(inner, font=(FONT, 9), bg=C["card"], fg=C["danger"], wraplength=260,
                       justify="left")
        err.grid(row=20, column=0, sticky="w", pady=(10, 0))

        def save(_e=None):
            data, problem = self.parse_product(v["id"].get(), v["name"].get(),
                                               v["price"].get(), v["qty"].get())
            if not problem and self.app.db.product(data[0]):
                problem = f"ID '{data[0]}' already exists."
            if problem:
                err.config(text=problem)
                return
            self.app.db.add_product(*data)
            win.destroy()
            self.clear(quiet=True)
            self.say(f"Added {data[1]}.")
            self.refresh()

        row = tk.Frame(inner, bg=C["card"])
        row.grid(row=21, column=0, sticky="ew", pady=(14, 0))
        row.columnconfigure((0, 1), weight=1)
        FlatButton(row, "Add product", save, bg=C["success"], hover=C["success_dark"]
                   ).grid(row=0, column=0, sticky="ew", padx=(0, 5))
        FlatButton(row, "Cancel", win.destroy, bg=C["bg"], fg=C["text"], hover=C["border"]
                   ).grid(row=0, column=1, sticky="ew", padx=(5, 0))
        win.bind("<Return>", save)
        win.bind("<Escape>", lambda e: win.destroy())
        first.focus_set()
        center_window(win, self)
        win.grab_set()

    def add(self):
        data = self.read_form()
        if not data or not self.can_edit():
            return
        if self.app.db.product(data[0]):
            return self.say(f"ID '{data[0]}' already exists.", False)
        self.app.db.add_product(*data)
        self.clear(quiet=True)
        self.say(f"Added {data[1]}.")
        self.refresh()

    def update(self):
        data = self.read_form() if self.selected_id is not None else None
        if not data or not self.can_edit():
            return
        if data[0] != self.selected_id and self.app.db.product(data[0]):
            return self.say(f"ID '{data[0]}' already exists.", False)
        self.app.db.update_product(self.selected_id, *data)
        self.clear(quiet=True)
        self.say(f"Saved {data[1]}.")
        self.refresh()

    def delete(self):
        if self.selected_id is None or not self.can_edit():
            return
        if messagebox.askyesno("Delete product", f"Delete '{self.v_name.get()}' permanently?",
                               parent=self):
            self.app.db.delete_product(self.selected_id)
            self.clear(quiet=True)
            self.say("Product deleted.")
            self.refresh()

    def clear(self, quiet=False):
        if self.readonly:
            return
        self.selected_id = None
        for v in (self.v_id, self.v_name, self.v_price, self.v_qty):
            v.set("")
        self.tree.selection_remove(self.tree.selection())
        self.set_mode(False)
        if not quiet:
            self.say("")

    def on_select(self, _e=None):
        sel = self.tree.selection()
        if self.readonly or not sel:
            return
        pid, name, price, qty, _ = self.tree.item(sel[0], "values")
        self.selected_id = str(pid)
        self.v_id.set(pid)
        self.v_name.set(name)
        self.v_price.set(f"{to_float(price.replace(CURRENCY, '')):.2f}")
        self.v_qty.set(qty)
        self.set_mode(True)
        self.say("")

    def sort_by(self, col):
        self.sort_rev = (not self.sort_rev) if self.sort_col == col else False
        self.sort_col = col
        self.refresh()

    @staticmethod
    def status_of(qty):
        return "Out" if qty <= 0 else "Low" if qty <= LOW_STOCK_LEVEL else "OK"

    def refresh(self):
        items = self.app.db.products(self.v_search.get())
        idx = {"id": 0, "name": 1, "price": 2, "qty": 3, "status": 3}[self.sort_col]
        items.sort(key=(lambda i: str(i[idx]).lower()) if idx < 2 else (lambda i: i[idx]),
                   reverse=self.sort_rev)
        keep = self.selected_id
        self.tree.delete(*self.tree.get_children())
        for n, (pid, name, price, qty) in enumerate(items):
            st = self.status_of(qty)
            tag = "out" if st == "Out" else "low" if st == "Low" else ("odd" if n % 2 else "")
            iid = self.tree.insert("", "end", values=(pid, name, money(price), qty, st),
                                   tags=(tag,) if tag else ())
            if keep is not None and str(pid) == keep:
                self.tree.selection_set(iid)
        self.count_lbl.config(text=f"{len(items)} product{'s' if len(items) != 1 else ''}")

    def export_csv(self):
        path = filedialog.asksaveasfilename(defaultextension=".csv", initialfile="inventory.csv",
                                            filetypes=[("CSV file", "*.csv")], parent=self)
        if path:
            with open(path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["Product ID", "Name", "Price", "Quantity"])
                w.writerows(self.app.db.products())
            self.say(f"Exported to {os.path.basename(path)}")


# Point of Sale
class POSPage(tk.Frame):
    """Counter sales for salespeople (admins do not have this page)."""

    def __init__(self, parent, app):
        super().__init__(parent, bg=C["bg"])
        self.app = app
        self.cart, self.all_labels = [], {}
        self.v_prod, self.v_qty = tk.StringVar(), tk.StringVar(value="1")
        self.v_discount = tk.StringVar(value="0")
        self.v_discount.trace_add("write", lambda *_: self.update_totals())

        page_header(self, "Point of Sale", "Ring up a customer, apply a discount and check out"
                    ).pack(fill="x", pady=(0, 14))
        body = tk.Frame(self, bg=C["bg"])
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=1)
        body.rowconfigure(0, weight=1)

        cart_card = Card(body)
        cart_card.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
        tk.Label(cart_card, text="Current bill", font=(FONT, 12, "bold"), bg=C["card"],
                 fg=C["text"]).pack(anchor="w", padx=14, pady=(14, 6))
        f, self.tree = make_tree(
            cart_card, [("id", "ID"), ("name", "Product"), ("price", "Price"), ("qty", "Qty"),
                        ("total", "Total")],
            [80, 140, 90, 50, 90], {"price": "e", "qty": "e", "total": "e"}, height=12)
        f.pack(fill="both", expand=True, padx=14)
        row = tk.Frame(cart_card, bg=C["card"])
        row.pack(fill="x", padx=14, pady=10)
        FlatButton(row, "Remove selected", self.remove_selected, bg=C["bg"], fg=C["text"],
                   hover=C["border"], pady=6).pack(side="left")
        FlatButton(row, "Clear bill", self.clear_cart, bg=C["bg"], fg=C["text"],
                   hover=C["border"], pady=6).pack(side="left", padx=8)
        tk.Label(row, text="Double-click a line to change its quantity", font=(FONT, 9),
                 bg=C["card"], fg=C["muted"]).pack(side="right")
        self.tree.bind("<Double-1>", lambda e: self.edit_qty())

        side = Card(body)
        side.grid(row=0, column=1, sticky="ns")
        inner = tk.Frame(side, bg=C["card"])
        inner.pack(padx=18, pady=16)
        inner.columnconfigure(0, weight=1)
        tk.Label(inner, text="Add item", font=(FONT, 13, "bold"), bg=C["card"], fg=C["text"]
                 ).grid(row=0, column=0, sticky="w")
        tk.Label(inner, text="PRODUCT (type to search)", font=(FONT, 9, "bold"), bg=C["card"],
                 fg=C["muted"]).grid(row=1, column=0, sticky="w", pady=(10, 2))
        self.combo = ttk.Combobox(inner, textvariable=self.v_prod, width=30,
                                  style="Modern.TCombobox")
        self.combo.grid(row=2, column=0, sticky="ew")
        self.combo.bind("<KeyRelease>", self.filter_combo)
        self.combo.bind("<<ComboboxSelected>>", lambda e: self.show_info())
        self.info = tk.Label(inner, font=(FONT, 9), bg=C["card"], fg=C["muted"], anchor="w")
        self.info.grid(row=3, column=0, sticky="w", pady=(4, 0))
        tk.Label(inner, text="QUANTITY", font=(FONT, 9, "bold"), bg=C["card"], fg=C["muted"]
                 ).grid(row=4, column=0, sticky="w", pady=(10, 2))
        q = ttk.Spinbox(inner, from_=1, to=9999, textvariable=self.v_qty, width=8,
                        style="Modern.TSpinbox")
        q.grid(row=5, column=0, sticky="w")
        q.bind("<Return>", lambda e: self.add_item())
        FlatButton(inner, "Add to bill", self.add_item).grid(row=6, column=0, sticky="ew",
                                                             pady=(14, 0))
        tk.Frame(inner, bg=C["border"], height=1).grid(row=7, column=0, sticky="ew", pady=18)

        def line(r, text, big=False):
            tk.Label(inner, text=text, font=(FONT, 11 if big else 10, "bold" if big else "normal"),
                     bg=C["card"], fg=C["text"] if big else C["muted"]
                     ).grid(row=r, column=0, sticky="w")
            v = tk.Label(inner, text=money(0), font=(FONT, 18 if big else 10, "bold"),
                         bg=C["card"], fg=C["text"], anchor="e")
            v.grid(row=r, column=0, sticky="e")
            return v

        self.l_sub = line(8, "Subtotal")
        dr = tk.Frame(inner, bg=C["card"])
        dr.grid(row=9, column=0, sticky="ew", pady=6)
        tk.Label(dr, text="Discount %", font=(FONT, 10), bg=C["card"], fg=C["muted"]).pack(side="left")
        self.l_disc = tk.Label(dr, text=money(0), font=(FONT, 10, "bold"), bg=C["card"],
                               fg=C["danger"])
        self.l_disc.pack(side="right")
        ttk.Entry(dr, textvariable=self.v_discount, width=5, justify="center",
                  style="Modern.TEntry").pack(side="right", padx=8)
        self.l_total = line(10, "TOTAL", big=True)
        FlatButton(inner, "Checkout", self.checkout, bg=C["success"], hover=C["success_dark"],
                   pady=11, font_size=11).grid(row=11, column=0, sticky="ew", pady=(16, 0))
        self.msg = tk.Label(inner, font=(FONT, 9), bg=C["card"], fg=C["muted"], wraplength=240,
                            justify="left")
        self.msg.grid(row=12, column=0, sticky="w", pady=(10, 0))

    def load_products(self):
        self.all_labels = {f"{pid} - {name}": pid for pid, name, _, _ in sorted(self.app.db.products())}
        self.combo["values"] = list(self.all_labels)

    def filter_combo(self, event):
        if event.keysym in ("Up", "Down", "Return", "Escape", "Tab"):
            return
        text = self.v_prod.get().lower()
        self.combo["values"] = [l for l in self.all_labels if text in l.lower()]
        self.show_info()

    def current_product(self):
        text = self.v_prod.get().strip()
        pid = self.all_labels.get(text)
        if pid is None:
            pid = next((p for p in self.all_labels.values() if p.lower() == text.lower()), None)
        return self.app.db.product(pid) if pid is not None else None

    def show_info(self):
        p = self.current_product()
        self.info.config(text=f"Price {money(p[2])}   |   In stock: {p[3]}" if p else "")

    def say(self, text, ok=True):
        self.msg.config(text=text, fg=C["success"] if ok else C["danger"])

    def add_item(self):
        p = self.current_product()
        if not p:
            return self.say("Pick a product from the list first.", False)
        qty = to_int(self.v_qty.get(), 0)
        if qty <= 0:
            return self.say("Quantity must be at least 1.", False)
        existing = next((l for l in self.cart if l["id"] == p[0]), None)
        wanted = qty + (existing["qty"] if existing else 0)
        if wanted > p[3]:
            return self.say(f"Only {p[3]} of {p[1]} in stock.", False)
        if existing:
            existing["qty"] = wanted
        else:
            self.cart.append({"id": p[0], "name": p[1], "price": p[2], "qty": qty})
        self.v_prod.set("")
        self.v_qty.set("1")
        self.info.config(text="")
        self.combo["values"] = list(self.all_labels)
        self.say(f"Added {qty} x {p[1]}.")
        self.render_cart()
        self.combo.focus_set()

    def edit_qty(self):
        sel = self.tree.selection()
        if not sel:
            return
        line = self.cart[self.tree.index(sel[0])]
        win = tk.Toplevel(self)
        win.title("Change quantity")
        win.configure(bg=C["card"])
        win.resizable(False, False)
        win.transient(self.winfo_toplevel())
        tk.Label(win, text=line["name"], font=(FONT, 11, "bold"), bg=C["card"]).pack(padx=20, pady=(16, 6))
        v = tk.StringVar(value=str(line["qty"]))
        sp = ttk.Spinbox(win, from_=1, to=9999, textvariable=v, width=8, style="Modern.TSpinbox")
        sp.pack(pady=4)
        sp.focus_set()

        def ok(_e=None):
            n, stock = to_int(v.get(), 0), self.app.db.product(line["id"])
            if n <= 0:
                self.say("Quantity must be at least 1.", False)
            elif stock and n > stock[3]:
                self.say(f"Only {stock[3]} of {line['name']} in stock.", False)
            else:
                line["qty"] = n
                self.render_cart()
            win.destroy()

        sp.bind("<Return>", ok)
        FlatButton(win, "Update", ok, pady=6).pack(padx=20, pady=(8, 16))
        center_window(win, self)
        win.grab_set()

    def remove_selected(self):
        sel = self.tree.selection()
        if sel:
            del self.cart[self.tree.index(sel[0])]
            self.render_cart()

    def clear_cart(self):
        self.cart.clear()
        self.render_cart()

    def render_cart(self):
        self.tree.delete(*self.tree.get_children())
        for n, l in enumerate(self.cart):
            self.tree.insert("", "end", tags=("odd",) if n % 2 else (),
                             values=(l["id"], l["name"], money(l["price"]), l["qty"],
                                     money(l["price"] * l["qty"])))
        self.update_totals()

    def totals(self):
        sub = sum(l["price"] * l["qty"] for l in self.cart)
        pct = min(max(to_float(self.v_discount.get()), 0.0), 100.0)
        return sub, pct, sub * pct / 100.0, sub - sub * pct / 100.0

    def update_totals(self):
        sub, _, disc, total = self.totals()
        self.l_sub.config(text=money(sub))
        self.l_disc.config(text="-" + money(disc))
        self.l_total.config(text=money(total))

    def checkout(self):
        if self.app.user["role"] != "salesperson":
            return self.say("Only salespeople can use the point of sale.", False)
        if not self.cart:
            return self.say("The bill is empty.", False)
        try:
            sale_id, sub, disc, total = self.app.db.checkout(self.cart, self.totals()[1], self.app.user)
        except ValueError as err:
            return self.say(str(err), False)
        receipt = self.build_receipt(sale_id, sub, disc, total)
        self.cart.clear()
        self.v_discount.set("0")
        self.render_cart()
        self.load_products()
        self.say(f"Sale #{sale_id} completed.")
        ReceiptWindow(self, receipt)

    def build_receipt(self, sale_id, sub, disc, total):
        w = 44
        lines = [APP_TITLE.center(w), f"Sale #{sale_id}".center(w),
                 datetime.now().strftime("%Y-%m-%d %H:%M").center(w),
                 f"Served by {self.app.user['full_name']}".center(w), "-" * w]
        for l in self.cart:
            lines.append(l["name"][:w])
            lines.append(f"   {l['qty']} x {money(l['price'])}".ljust(w - 14)
                         + money(l["price"] * l["qty"]).rjust(14))
        lines += ["-" * w, "Subtotal".ljust(w - 14) + money(sub).rjust(14)]
        if disc:
            lines.append("Discount".ljust(w - 14) + ("-" + money(disc)).rjust(14))
        lines += ["TOTAL".ljust(w - 14) + money(total).rjust(14), "-" * w, "Thank you!".center(w)]
        return "\n".join(lines)


class ReceiptWindow(tk.Toplevel):
    def __init__(self, parent, text):
        super().__init__(parent)
        self.title("Receipt")
        self.configure(bg=C["card"])
        self.transient(parent.winfo_toplevel())
        t = tk.Text(self, width=46, height=min(30, text.count("\n") + 2), font=("Courier", 10),
                    bd=0, bg="#fffef7", padx=12, pady=12)
        t.insert("1.0", text)
        t.config(state="disabled")
        t.pack(padx=16, pady=(16, 8))
        row = tk.Frame(self, bg=C["card"])
        row.pack(pady=(0, 16))
        FlatButton(row, "Save as text file", lambda: self.save(text), pady=6).pack(side="left", padx=4)
        FlatButton(row, "Close", self.destroy, bg=C["bg"], fg=C["text"], hover=C["border"],
                   pady=6).pack(side="left", padx=4)
        center_window(self, parent)
        self.grab_set()

    def save(self, text):
        path = filedialog.asksaveasfilename(defaultextension=".txt", initialfile="receipt.txt",
                                            filetypes=[("Text file", "*.txt")], parent=self)
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)


#  Sales history
class SalesPage(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=C["bg"])
        self.app = app
        self.only_mine = app.user["role"] == "salesperson" and not config.SALESPERSON_SEES_ALL_SALES
        top = tk.Frame(self, bg=C["bg"])
        top.pack(fill="x", pady=(0, 14))
        page_header(top, "Sales history",
                    "The sales you have made - select one to see its items" if self.only_mine
                    else "Every point-of-sale transaction - select one to see its items"
                    ).pack(side="left")
        self.summary = tk.Label(top, font=(FONT, 11, "bold"), bg=C["bg"], fg=C["text"])
        self.summary.pack(side="right")
        body = tk.Frame(self, bg=C["bg"])
        body.pack(fill="both", expand=True)
        body.columnconfigure((0, 1), weight=1, uniform="s")
        body.rowconfigure(0, weight=1)
        a = Card(body)
        a.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        f, self.tree = make_tree(a, [("id", "#"), ("date", "Date"), ("by", "Cashier"),
                                     ("disc", "Discount"), ("total", "Total")],
                                 [40, 120, 90, 70, 90], {"disc": "e", "total": "e"}, height=16)
        f.pack(fill="both", expand=True, padx=14, pady=14)
        self.tree.bind("<<TreeviewSelect>>", self.show_items)
        b = Card(body)
        b.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        self.title = tk.Label(b, text="Items", font=(FONT, 12, "bold"), bg=C["card"], fg=C["text"])
        self.title.pack(anchor="w", padx=14, pady=(14, 6))
        f, self.items = make_tree(b, [("name", "Product"), ("price", "Price"), ("qty", "Qty"),
                                      ("total", "Total")], [170, 80, 50, 90],
                                  {"price": "e", "qty": "e", "total": "e"}, height=16)
        f.pack(fill="both", expand=True, padx=14, pady=(0, 14))

    def refresh(self):
        rows = self.app.db.recent_sales(cashier_id=self.app.user["id"] if self.only_mine else None)
        self.tree.delete(*self.tree.get_children())
        for n, s in enumerate(rows):
            self.tree.insert("", "end", iid=str(s["id"]), tags=("odd",) if n % 2 else (),
                             values=(s["id"], s["created"][:16], s["cashier"] or "-",
                                     money(s["discount"]), money(s["total"])))
        self.items.delete(*self.items.get_children())
        self.title.config(text="Items")
        self.summary.config(text=f"{len(rows)} sales  •  {money(sum(s['total'] for s in rows))}")

    def show_items(self, _e=None):
        sel = self.tree.selection()
        if not sel:
            return
        self.title.config(text=f"Items in sale #{sel[0]}")
        self.items.delete(*self.items.get_children())
        for n, it in enumerate(self.app.db.sale_items(int(sel[0]))):
            self.items.insert("", "end", tags=("odd",) if n % 2 else (),
                              values=(it["name"], money(it["price"]), it["qty"], money(it["line_total"])))


# ================================================================================== Users
class UsersPage(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=C["bg"])
        self.app = app
        top = tk.Frame(self, bg=C["bg"])
        top.pack(fill="x", pady=(0, 14))
        page_header(top, "Users", "Everyone who has an account - admins, salespeople and customers"
                    ).pack(side="left")
        FlatButton(top, "Remove selected user", self.remove, bg=C["danger"], hover=C["danger_dark"]
                   ).pack(side="right")
        card = Card(self)
        card.pack(fill="both", expand=True)
        f, self.tree = make_tree(card, [("name", "Name"), ("user", "Username"), ("role", "Role"),
                                        ("phone", "Phone"), ("state", "State"), ("joined", "Joined")],
                                 [180, 130, 100, 120, 100, 120], height=18)
        f.pack(fill="both", expand=True, padx=14, pady=14)
        self.msg = tk.Label(self, font=(FONT, 9), bg=C["bg"], fg=C["muted"])
        self.msg.pack(anchor="w", pady=(8, 0))

    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        for n, u in enumerate(self.app.db.users()):
            self.tree.insert("", "end", iid=str(u["id"]), tags=("odd",) if n % 2 else (),
                             values=(u["full_name"], u["username"], u["role"].title(),
                                     u["phone"] or "-", u["state"] or "-", u["created"][:10]))

    def remove(self):
        sel = self.tree.selection()
        if not sel:
            return self.msg.config(text="Select a user first.", fg=C["danger"])
        uid = int(sel[0])
        if uid == self.app.user["id"]:
            return self.msg.config(text="You can't remove your own account.", fg=C["danger"])
        name = self.tree.item(sel[0], "values")[0]
        if messagebox.askyesno("Remove user", f"Remove {name}'s account?", parent=self):
            self.app.db.delete_user(uid)
            self.msg.config(text=f"Removed {name}.", fg=C["success"])
            self.refresh()


# ============================================================================== Warehouses
class WarehousesPage(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=C["bg"])
        self.app, self.sel = app, None
        self.v = {k: tk.StringVar() for k in ("name", "address", "phone")}
        page_header(self, "Warehouses", "One warehouse in every Nigerian state and the FCT"
                    ).pack(fill="x", pady=(0, 14))
        body = tk.Frame(self, bg=C["bg"])
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=1)
        body.rowconfigure(0, weight=1)
        card = Card(body)
        card.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
        f, self.tree = make_tree(card, [("state", "State"), ("name", "Warehouse"), ("wh", "Waiting"),
                                        ("tr", "Transit"), ("dl", "Done")],
                                 [90, 170, 70, 70, 60], {"wh": "e", "tr": "e", "dl": "e"}, height=18)
        f.pack(fill="both", expand=True, padx=14, pady=14)
        self.tree.bind("<<TreeviewSelect>>", self.on_select)
        side = Card(body)
        side.grid(row=0, column=1, sticky="ns")
        inner = tk.Frame(side, bg=C["card"])
        inner.pack(padx=18, pady=16)
        inner.columnconfigure(0, weight=1)
        self.title = tk.Label(inner, text="Select a warehouse", font=(FONT, 13, "bold"),
                              bg=C["card"], fg=C["text"])
        self.title.grid(row=0, column=0, sticky="w")
        labeled_entry(inner, "WAREHOUSE NAME", self.v["name"], 1, 26)
        labeled_entry(inner, "ADDRESS", self.v["address"], 2, 26)
        labeled_entry(inner, "PHONE", self.v["phone"], 3, 26)
        FlatButton(inner, "Save changes", self.save, bg=C["success"], hover=C["success_dark"]
                   ).grid(row=20, column=0, sticky="ew", pady=(20, 6))
        FlatButton(inner, "View orders here", self.view_orders).grid(row=21, column=0, sticky="ew")
        self.msg = tk.Label(inner, font=(FONT, 9), bg=C["card"], fg=C["muted"], wraplength=210,
                            justify="left")
        self.msg.grid(row=22, column=0, sticky="w", pady=(12, 0))

    def refresh(self):
        keep = self.sel
        self.tree.delete(*self.tree.get_children())
        for n, w in enumerate(self.app.db.warehouse_summary()):
            self.tree.insert("", "end", iid=str(w["id"]), tags=("odd",) if n % 2 else (),
                             values=(w["state"], w["name"], w["n_wh"], w["n_tr"], w["n_dl"]))
        if keep and self.tree.exists(str(keep)):
            self.tree.selection_set(str(keep))

    def on_select(self, _e=None):
        sel = self.tree.selection()
        if not sel:
            return
        w = self.app.db.warehouse(int(sel[0]))
        self.sel = w["id"]
        self.title.config(text=f"{w['state']} - {w['city']}")
        self.v["name"].set(w["name"])
        self.v["address"].set(w["address"])
        self.v["phone"].set(w["phone"] or "")
        self.msg.config(text="")

    def save(self):
        if not self.sel:
            return self.msg.config(text="Select a warehouse first.", fg=C["danger"])
        if not self.v["name"].get().strip():
            return self.msg.config(text="Name can't be empty.", fg=C["danger"])
        self.app.db.update_warehouse(self.sel, self.v["name"].get().strip(),
                                     self.v["address"].get().strip(), self.v["phone"].get().strip())
        self.msg.config(text="Saved.", fg=C["success"])
        self.refresh()

    def view_orders(self):
        if self.sel:
            self.app.show("Shipping & Orders", wid=self.sel)
