import tkinter as tk
from tkinter import messagebox, ttk

from database import STATES
from ui import (C, FONT, ROLE_COLOUR, STATUS_STYLE, Card, FlatButton, Segmented, center_window,
                make_tree, money, page_header, stat_cards, to_int)


#  order detail view
def make_detail(parent):
    t = tk.Text(parent, width=34, bd=0, bg=C["card"], padx=16, pady=12, wrap="word",
                cursor="arrow", highlightthickness=0, height=12, tabs=("262", "right"),
                font=(FONT, 10))
    t.tag_configure("h", font=(FONT, 15, "bold"), foreground=C["text"])
    t.tag_configure("b", font=(FONT, 10, "bold"), foreground=C["text"])
    t.tag_configure("m", foreground=C["muted"], font=(FONT, 9))
    t.tag_configure("sec", font=(FONT, 9, "bold"), foreground=C["muted"], spacing1=9, spacing3=2)
    for name, (_, bg, fg) in STATUS_STYLE.items():
        t.tag_configure("s_" + name.replace(" ", "_"), background=bg, foreground=fg, font=(FONT, 10, "bold"))
    t.config(state="disabled")
    return t


def render_order(text, db, oid):
    text.config(state="normal")
    text.delete("1.0", "end")
    o = db.order(oid) if oid else None
    if not o:
        text.insert("end", "Select an order to see its details and tracking.", "m")
        text.config(state="disabled")
        return
    w = lambda s, tag=(): text.insert("end", s, tag)
    w(f"Order #{o['id']}\n", "h")
    w(f" {o['status']} ", "s_" + o["status"].replace(" ", "_"))
    w(f"   placed {o['created'][:16]}\n", "m")
    w("CUSTOMER\n", "sec")
    w(f"{o['customer']}\n", "b")
    w(f"{o['phone'] or 'No phone'}\n{o['address']}, {o['state']}\n", "m")
    w("PICK-UP WAREHOUSE\n", "sec")
    w(f"{o['wh_name']}\n", "b")
    w(f"{o['wh_address']}\n" + (f"{o['wh_phone']}\n" if o["wh_phone"] else ""), "m")
    w("ITEMS\n", "sec")
    for it in db.order_items(oid):
        w(f"{it['name']}  x{it['qty']}\t{money(it['price'] * it['qty'])}\n")
    w("Total\t" + money(o["total"]) + "\n", "b")
    w("TRACKING\n", "sec")
    for ev in db.order_events(oid):
        w(f"●  {ev['status']}", "b")
        w(f"   {ev['at'][5:16]} · {ev['actor']}\n", "m")
    text.config(state="disabled")


#  location filter
class LocationDialog(tk.Toplevel):
    def __init__(self, parent, db, current, on_pick):
        super().__init__(parent)
        self.title("Filter by location")
        self.configure(bg=C["card"])
        self.transient(parent.winfo_toplevel())
        self.on_pick, self.rows, self.shown = on_pick, db.warehouse_summary(), []
        tk.Label(self, text="Choose a warehouse location", font=(FONT, 14, "bold"), bg=C["card"],
                 fg=C["text"]).pack(anchor="w", padx=22, pady=(18, 2))
        tk.Label(self, text="See the status of products and orders at one location",
                 font=(FONT, 9), bg=C["card"], fg=C["muted"]).pack(anchor="w", padx=22)
        self.q = tk.StringVar()
        self.q.trace_add("write", lambda *_: self.fill())
        e = ttk.Entry(self, textvariable=self.q, style="Modern.TEntry")
        e.pack(fill="x", padx=22, pady=(12, 8))
        frame = tk.Frame(self, bg=C["card"])
        frame.pack(fill="both", expand=True, padx=22)
        self.lb = tk.Listbox(frame, height=14, width=44, font=(FONT, 10), bd=0, activestyle="none",
                             highlightthickness=1, highlightbackground=C["border"],
                             selectbackground=C["accent"], selectforeground="white")
        sb = ttk.Scrollbar(frame, orient="vertical", command=self.lb.yview)
        self.lb.config(yscrollcommand=sb.set)
        self.lb.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.lb.bind("<Double-1>", lambda e: self.apply())
        row = tk.Frame(self, bg=C["card"])
        row.pack(fill="x", padx=22, pady=16)
        FlatButton(row, "Apply filter", self.apply, pady=7).pack(side="left")
        FlatButton(row, "Cancel", self.destroy, bg=C["bg"], fg=C["text"], hover=C["border"],
                   pady=7).pack(side="left", padx=8)
        self.fill()
        e.focus_set()
        e.bind("<Return>", lambda ev: self.apply())
        self.bind("<Escape>", lambda ev: self.destroy())
        center_window(self, parent)
        self.grab_set()

    def fill(self):
        s = self.q.get().strip().lower()
        self.lb.delete(0, "end")
        self.shown = [None] + [r for r in self.rows
                               if s in r["state"].lower() or s in r["city"].lower()
                               or s in r["name"].lower()]
        for r in self.shown:
            if r is None:
                self.lb.insert("end", "All locations")
            else:
                n = r["n_wh"] + r["n_tr"] + r["n_dl"]
                self.lb.insert("end", f"{r['state']}  -  {r['name']}   ({n} order{'s' if n != 1 else ''})")
        self.lb.selection_set(0)

    def apply(self):
        sel = self.lb.curselection()
        if sel:
            r = self.shown[sel[0]]
            self.on_pick(r["id"] if r else None)
        self.destroy()


#  Shipping & Orders
class ShippingPage(tk.Frame):
    """For admins and salespeople: follow every order from warehouse to delivery."""
    FILTERS = ["All", "In Warehouse", "In Transit", "Delivered", "Cancelled"]

    def __init__(self, parent, app):
        super().__init__(parent, bg=C["bg"])
        self.app, self.wid, self.status, self.sel = app, None, "All", None
        self.q = tk.StringVar()
        self.q.trace_add("write", lambda *_: self.refresh())
        colour = ROLE_COLOUR[app.user["role"]]

        top = tk.Frame(self, bg=C["bg"])
        top.pack(fill="x", pady=(0, 12))
        page_header(top, "Shipping & Orders",
                    "Is it still in the warehouse, in transit or delivered?").pack(side="left")
        FlatButton(top, "Filter by location", self.pick_location, bg=colour, hover=colour
                   ).pack(side="right")
        self.chip = tk.Label(top, font=(FONT, 9, "bold"), bg="#e0e7ff", fg=C["accent"], padx=12,
                             pady=8, cursor="hand2")
        self.chip.bind("<Button-1>", lambda e: self.set_location(None))
        self.chip_pad = 10

        f, self.s = stat_cards(self, [("all", "Orders", "#64748b"), ("wh", "In warehouse", "#d97706"),
                                      ("tr", "In transit", "#2563eb"), ("dl", "Delivered", C["success"])])
        f.pack(fill="x")
        bar = tk.Frame(self, bg=C["bg"])
        bar.pack(fill="x", pady=(12, 10))
        self.seg = Segmented(bar, self.FILTERS, command=self.set_status, accent=colour)
        self.seg.pack(side="left")
        ttk.Entry(bar, textvariable=self.q, width=28, style="Modern.TEntry").pack(side="right")
        tk.Label(bar, text="Search order, customer, product", font=(FONT, 9), bg=C["bg"],
                 fg=C["muted"]).pack(side="right", padx=8)

        body = tk.Frame(self, bg=C["bg"])
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=1)
        body.rowconfigure(0, weight=1)
        card = Card(body)
        card.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        f, self.tree = make_tree(card, [("id", "Order"), ("items", "Product(s)"), ("cust", "Customer"),
                                        ("wh", "Warehouse"), ("st", "Status")],
                                 [50, 170, 100, 110, 90], height=12)
        f.pack(fill="both", expand=True, padx=12, pady=12)
        self.tree.bind("<<TreeviewSelect>>", self.on_select)

        det = Card(body)
        det.grid(row=0, column=1, sticky="ns")
        self.btns = tk.Frame(det, bg=C["card"])
        self.btns.pack(side="bottom", fill="x", padx=16, pady=(0, 14))
        self.detail = make_detail(det)
        self.detail.pack(side="top", fill="both", expand=True)
        self.btns.columnconfigure((0, 1), weight=1, uniform="b")
        self.b_transit = FlatButton(self.btns, "Mark In Transit", lambda: self.move("In Transit"),
                                    bg="#2563eb", hover="#1d4ed8", pady=7)
        self.b_done = FlatButton(self.btns, "Mark Delivered", lambda: self.move("Delivered"),
                                 bg=C["success"], hover=C["success_dark"], pady=7)
        self.b_cancel = FlatButton(self.btns, "Cancel order", lambda: self.move("Cancelled"),
                                   bg=C["bg"], fg=C["danger"], hover=C["out_bg"], pady=6)
        self.msg = tk.Label(self.btns, font=(FONT, 9), bg=C["card"], fg=C["danger"], wraplength=260)
        self.msg.grid(row=2, column=0, columnspan=2)

    def apply(self, wid=None):               
        self.set_location(wid)

    def pick_location(self):
        LocationDialog(self, self.app.db, self.wid, self.set_location)

    def set_location(self, wid):
        self.wid = wid
        self.chip.pack_forget()
        if wid:
            w = self.app.db.warehouse(wid)
            self.chip.config(text=f"Location: {w['state']}   ✕")
            self.chip.pack(side="right", padx=(0, self.chip_pad))
        self.refresh()

    def set_status(self, value):
        self.status = value
        self.refresh()

    def refresh(self):
        db = self.app.db
        oc = db.order_counts(wid=self.wid)
        self.s["all"].config(text=str(sum(oc.values())))
        self.s["wh"].config(text=str(oc["In Warehouse"]))
        self.s["tr"].config(text=str(oc["In Transit"]))
        self.s["dl"].config(text=str(oc["Delivered"]))
        rows = db.orders(wid=self.wid, status=None if self.status == "All" else self.status,
                         search=self.q.get())
        self.tree.delete(*self.tree.get_children())
        for o in rows:
            self.tree.insert("", "end", iid=str(o["id"]), tags=(STATUS_STYLE[o["status"]][0],),
                             values=(f"#{o['id']}", o["items"], o["customer"], o["wh_state"], o["status"]))
        if self.sel and self.tree.exists(str(self.sel)):
            self.tree.selection_set(str(self.sel))
        else:
            self.sel = None
        self.show_detail()

    def on_select(self, _e=None):
        sel = self.tree.selection()
        self.sel = int(sel[0]) if sel else None
        self.msg.config(text="")
        self.show_detail()

    def show_detail(self):
        render_order(self.detail, self.app.db, self.sel)
        for b in (self.b_transit, self.b_done, self.b_cancel):
            b.grid_remove()
        o = self.app.db.order(self.sel) if self.sel else None
        if o:
            nxt = self.app.db.NEXT[o["status"]]
            if "In Transit" in nxt:
                self.b_transit.grid(row=0, column=0, sticky="ew", padx=(0, 3))
            if "Delivered" in nxt:
                self.b_done.grid(row=0, column=1 if "In Transit" in nxt else 0,
                                 columnspan=1 if "In Transit" in nxt else 2, sticky="ew",
                                 padx=(3, 0) if "In Transit" in nxt else 0)
            if "Cancelled" in nxt:
                self.b_cancel.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(5, 0))

    def move(self, status):
        if not self.sel:
            return
        if status == "Cancelled" and not messagebox.askyesno(
                "Cancel order", f"Cancel order #{self.sel}? The items go back into stock.", parent=self):
            return
        try:
            self.app.db.set_status(self.sel, status, self.app.user["full_name"])
        except ValueError as e:
            return self.msg.config(text=str(e))
        self.msg.config(text="")
        self.refresh()


# Shop
class ShopPage(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=C["bg"])
        self.app, self.cart, self.wh_map = app, [], {}
        u = app.user
        self.v_search, self.v_qty = tk.StringVar(), tk.StringVar(value="1")
        self.v_state, self.v_addr = tk.StringVar(value=u.get("state") or ""), tk.StringVar()
        self.v_phone, self.v_wh = tk.StringVar(value=u.get("phone") or ""), tk.StringVar()
        self.v_search.trace_add("write", lambda *_: self.refresh())
        colour = ROLE_COLOUR["customer"]

        page_header(self, "Shop", "Pick what you need, tell us where you live and collect it from "
                                  "the nearest warehouse").pack(fill="x", pady=(0, 12))
        body = tk.Frame(self, bg=C["bg"])
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=1)
        body.rowconfigure(0, weight=1)

        left = Card(body)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        bar = tk.Frame(left, bg=C["card"])
        bar.pack(fill="x", padx=14, pady=(14, 8))
        tk.Label(bar, text="Search", font=(FONT, 9, "bold"), bg=C["card"], fg=C["muted"]).pack(side="left")
        ttk.Entry(bar, textvariable=self.v_search, style="Modern.TEntry").pack(
            side="left", fill="x", expand=True, padx=(8, 0))
        f, self.tree = make_tree(left, [("name", "Product"), ("price", "Price"), ("avail", "Available")],
                                 [190, 90, 80], {"price": "e", "avail": "e"}, height=12)
        f.pack(fill="both", expand=True, padx=14)
        row = tk.Frame(left, bg=C["card"])
        row.pack(fill="x", padx=14, pady=12)
        tk.Label(row, text="Quantity", font=(FONT, 9, "bold"), bg=C["card"], fg=C["muted"]).pack(side="left")
        ttk.Spinbox(row, from_=1, to=999, textvariable=self.v_qty, width=6,
                    style="Modern.TSpinbox").pack(side="left", padx=8)
        FlatButton(row, "Add to my order", self.add_item, bg=colour, hover=colour, pady=7
                   ).pack(side="left")
        self.tree.bind("<Double-1>", lambda e: self.add_item())

        right = Card(body)
        right.grid(row=0, column=1, sticky="ns")
        inner = tk.Frame(right, bg=C["card"])
        inner.pack(padx=16, pady=14)
        tk.Label(inner, text="Your order", font=(FONT, 13, "bold"), bg=C["card"], fg=C["text"]
                 ).pack(anchor="w")
        f, self.cart_tree = make_tree(inner, [("name", "Item"), ("qty", "Qty"), ("t", "Total")],
                                      [150, 40, 90], {"qty": "e", "t": "e"}, height=3)
        f.pack(fill="x", pady=(6, 0))
        self.cart_tree.bind("<Double-1>", lambda e: self.remove_selected())
        tk.Label(inner, text="Double-click a line to remove it", font=(FONT, 8), bg=C["card"],
                 fg=C["muted"]).pack(anchor="w")

        def field(label):
            tk.Label(inner, text=label, font=(FONT, 9, "bold"), bg=C["card"], fg=C["muted"]
                     ).pack(anchor="w", pady=(9, 2))

        field("YOUR STATE")
        st = ttk.Combobox(inner, textvariable=self.v_state, values=STATES, state="readonly",
                          style="Modern.TCombobox", width=30)
        st.pack(fill="x")
        st.bind("<<ComboboxSelected>>", lambda e: self.update_warehouses())
        field("YOUR ADDRESS / AREA")
        ttk.Entry(inner, textvariable=self.v_addr, style="Modern.TEntry").pack(fill="x")
        field("PHONE NUMBER")
        ttk.Entry(inner, textvariable=self.v_phone, style="Modern.TEntry").pack(fill="x")
        field("PICK-UP WAREHOUSE (nearest first)")
        self.wh_combo = ttk.Combobox(inner, textvariable=self.v_wh, state="readonly",
                                     style="Modern.TCombobox", width=30)
        self.wh_combo.pack(fill="x")
        self.wh_combo.bind("<<ComboboxSelected>>", lambda e: self.show_wh())
        self.wh_info = tk.Label(inner, font=(FONT, 9), bg=C["card"], fg=C["muted"], wraplength=290,
                                justify="left", anchor="w")
        self.wh_info.pack(anchor="w", pady=(4, 0))
        tot = tk.Frame(inner, bg=C["card"])
        tot.pack(fill="x", pady=(8, 0))
        tk.Label(tot, text="TOTAL", font=(FONT, 11, "bold"), bg=C["card"], fg=C["text"]).pack(side="left")
        self.total = tk.Label(tot, text=money(0), font=(FONT, 17, "bold"), bg=C["card"], fg=C["text"])
        self.total.pack(side="right")
        FlatButton(inner, "Place order", self.place, bg=C["success"], hover=C["success_dark"],
                   pady=10, font_size=11).pack(fill="x", pady=(8, 0))
        self.msg = tk.Label(inner, font=(FONT, 9), bg=C["card"], wraplength=290, justify="left")
        self.msg.pack(anchor="w", pady=(6, 0))
        self.update_warehouses()

    def say(self, text, ok=False):
        self.msg.config(text=text, fg=C["success"] if ok else C["danger"])

    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        n = 0
        for pid, name, price, qty in sorted(self.app.db.products(self.v_search.get()),
                                            key=lambda p: p[1].lower()):
            if qty > 0:
                self.tree.insert("", "end", iid=str(pid), tags=("odd",) if n % 2 else (),
                                 values=(name, money(price), qty))
                n += 1

    def update_warehouses(self):
        state = self.v_state.get()
        near = self.app.db.nearest_warehouses(state, 3) if state else []
        self.wh_map = {}
        for w, km in near:
            tail = "same state" if km is not None and km < 1 else (f"{km:.0f} km away" if km else "")
            self.wh_map[f"{w['name']} ({tail})" if tail else w["name"]] = w["id"]
        self.wh_combo["values"] = list(self.wh_map)
        self.v_wh.set(next(iter(self.wh_map), ""))
        self.show_wh()

    def show_wh(self):
        wid = self.wh_map.get(self.v_wh.get())
        w = self.app.db.warehouse(wid) if wid else None
        self.wh_info.config(text=f"{w['address']}" + (f"  •  {w['phone']}" if w["phone"] else "")
                            if w else "Select your state to see the closest warehouses.")

    def add_item(self):
        sel = self.tree.selection()
        if not sel:
            return self.say("Select a product first.")
        p = self.app.db.product(sel[0])
        qty = to_int(self.v_qty.get(), 0)
        if not p or qty <= 0:
            return self.say("Quantity must be at least 1.")
        line = next((l for l in self.cart if l["id"] == p[0]), None)
        wanted = qty + (line["qty"] if line else 0)
        if wanted > p[3]:
            return self.say(f"Only {p[3]} of {p[1]} available.")
        if line:
            line["qty"] = wanted
        else:
            self.cart.append({"id": p[0], "name": p[1], "price": p[2], "qty": qty})
        self.v_qty.set("1")
        self.say(f"Added {qty} x {p[1]}.", ok=True)
        self.render_cart()

    def remove_selected(self):
        sel = self.cart_tree.selection()
        if sel:
            del self.cart[self.cart_tree.index(sel[0])]
            self.render_cart()

    def render_cart(self):
        self.cart_tree.delete(*self.cart_tree.get_children())
        for n, l in enumerate(self.cart):
            self.cart_tree.insert("", "end", tags=("odd",) if n % 2 else (),
                                  values=(l["name"], l["qty"], money(l["price"] * l["qty"])))
        self.total.config(text=money(sum(l["price"] * l["qty"] for l in self.cart)))

    def place(self):
        state, addr, phone = self.v_state.get(), self.v_addr.get().strip(), self.v_phone.get().strip()
        wid = self.wh_map.get(self.v_wh.get())
        if not self.cart:
            return self.say("Add at least one item to your order.")
        if not state or not wid:
            return self.say("Choose your state so we can find the nearest warehouse.")
        if len(addr) < 3:
            return self.say("Please enter your address or area.")
        if len(phone) < 7:
            return self.say("Please enter a phone number we can reach you on.")
        try:
            oid = self.app.db.place_order(self.app.user, self.cart, state, addr, phone, wid)
        except ValueError as e:
            return self.say(str(e))
        self.app.db.update_user_location(self.app.user["id"], state, phone)
        self.app.user.update(state=state, phone=phone)
        w = self.app.db.warehouse(wid)
        self.cart.clear()
        self.render_cart()
        self.v_addr.set("")
        self.say("")
        messagebox.showinfo("Order placed",
                            f"Order #{oid} is confirmed and waiting in the warehouse.\n\n"
                            f"Pick-up point:\n{w['name']}\n{w['address']}\n\n"
                            "You can follow it under 'My Orders'.", parent=self)
        self.app.show("My Orders", select=oid)


#  My Orders 
class MyOrdersPage(tk.Frame):
    FILTERS = ["All", "In Warehouse", "In Transit", "Delivered", "Cancelled"]

    def __init__(self, parent, app):
        super().__init__(parent, bg=C["bg"])
        self.app, self.status, self.sel = app, "All", None
        colour = ROLE_COLOUR["customer"]
        page_header(self, "My Orders", "Track your orders - and see exactly where to collect them"
                    ).pack(fill="x", pady=(0, 12))
        Segmented(self, self.FILTERS, command=self.set_status, accent=colour).pack(anchor="w", pady=(0, 10))
        body = tk.Frame(self, bg=C["bg"])
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=1)
        body.rowconfigure(0, weight=1)
        card = Card(body)
        card.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        f, self.tree = make_tree(card, [("id", "Order"), ("items", "Items"), ("wh", "Pick-up"),
                                        ("st", "Status"), ("t", "Total")],
                                 [55, 190, 90, 90, 90], {"t": "e"}, height=14)
        f.pack(fill="both", expand=True, padx=12, pady=12)
        self.tree.bind("<<TreeviewSelect>>", self.on_select)
        det = Card(body)
        det.grid(row=0, column=1, sticky="ns")
        foot = tk.Frame(det, bg=C["card"])
        foot.pack(side="bottom", fill="x", padx=16, pady=(0, 14))
        self.detail = make_detail(det)
        self.detail.pack(side="top", fill="both", expand=True)
        self.cancel = FlatButton(foot, "Cancel this order", self.cancel_order, bg=C["bg"],
                                 fg=C["danger"], hover=C["out_bg"], pady=7)
        self.msg = tk.Label(foot, font=(FONT, 9), bg=C["card"], fg=C["danger"], wraplength=260)

    def apply(self, select=None):
        self.sel = select
        self.status = "All"

    def set_status(self, v):
        self.status = v
        self.refresh()

    def refresh(self):
        rows = self.app.db.orders(user_id=self.app.user["id"],
                                  status=None if self.status == "All" else self.status)
        self.tree.delete(*self.tree.get_children())
        for o in rows:
            self.tree.insert("", "end", iid=str(o["id"]), tags=(STATUS_STYLE[o["status"]][0],),
                             values=(f"#{o['id']}", o["items"], o["wh_state"], o["status"], money(o["total"])))
        if self.sel and self.tree.exists(str(self.sel)):
            self.tree.selection_set(str(self.sel))
        else:
            self.sel = None
        self.show_detail()

    def on_select(self, _e=None):
        sel = self.tree.selection()
        self.sel = int(sel[0]) if sel else None
        self.msg.pack_forget()
        self.show_detail()

    def show_detail(self):
        render_order(self.detail, self.app.db, self.sel)
        self.cancel.pack_forget()
        o = self.app.db.order(self.sel) if self.sel else None
        if o and o["status"] == "In Warehouse":
            self.cancel.pack(fill="x")

    def cancel_order(self):
        o = self.app.db.order(self.sel) if self.sel else None
        if not o or o["user_id"] != self.app.user["id"]:
            return
        if messagebox.askyesno("Cancel order", f"Cancel order #{o['id']}?", parent=self):
            try:
                self.app.db.set_status(o["id"], "Cancelled", self.app.user["full_name"])
            except ValueError as e:
                self.msg.config(text=str(e))
                self.msg.pack()
            self.refresh()
