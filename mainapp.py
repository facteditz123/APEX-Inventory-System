import tkinter as tk

import config
from analytics import AnalyticsPage, export_all
from auth import AuthScreen
from dashboards import AdminDashboard, CustomerDashboard, SalesDashboard
from database import Database
from orders import MyOrdersPage, ShippingPage, ShopPage
from staff_pages import InventoryPage, POSPage, SalesPage, UsersPage, WarehousesPage
from ui import C, FONT, ROLE_COLOUR, ROLE_LABEL, FlatButton, setup_styles

PAGES = {
    "admin": [
        ("Dashboard", AdminDashboard),
        ("Inventory", lambda p, a: InventoryPage(p, a)),
        ("Analytics", AnalyticsPage),
        ("Shipping & Orders", ShippingPage),
        ("Warehouses", WarehousesPage),
        ("Sales History", SalesPage),
        ("Users", UsersPage),
    ],
    "salesperson": [
        ("Dashboard", SalesDashboard),
        ("Point of Sale", POSPage),
        ("Products", lambda p, a: InventoryPage(p, a, readonly=True)),
        ("Shipping & Orders", ShippingPage),
        ("Sales History", SalesPage),
    ],
    "customer": [
        ("Dashboard", CustomerDashboard),
        ("Shop", ShopPage),
        ("My Orders", MyOrdersPage),
    ],
}
SUBTITLE = {"admin": "Admin portal", "salesperson": "Salesperson portal", "customer": "Customer portal"}


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(config.APP_TITLE)
        self.configure(bg=C["bg"])
        setup_styles(self)
        self.db = Database(config.DB_FILE)
        self.user, self.shell, self.auth, self.current = None, None, None, None
        self.pages, self.nav = {}, {}
        self.export_job = None
        self.db.listeners.append(self.queue_export)      
        self.show_auth()

    def queue_export(self):
        """Rewrite the CSV files shortly after any change (batches bursts of changes)."""
        if config.AUTO_EXPORT and self.export_job is None:
            self.export_job = self.after(800, self.run_export)

    def run_export(self):
        self.export_job = None
        try:
            export_all(self.db, config.EXPORT_FOLDER)
        except OSError:
            pass

    #  windows
    def place_window(self, w, h, min_size):
        self.update_idletasks()
        w, h = min(w, self.winfo_screenwidth() - 40), min(h, self.winfo_screenheight() - 90)
        x, y = (self.winfo_screenwidth() - w) // 2, max((self.winfo_screenheight() - h) // 3, 0)
        self.geometry(f"{w}x{h}+{x}+{y}")
        self.minsize(min(min_size[0], w), min(min_size[1], h))

    def show_auth(self):
        if self.shell:
            self.shell.destroy()
            self.shell = None
        self.user, self.current = None, None
        self.place_window(1040, 700, (940, 660))
        self.auth = AuthScreen(self, self)
        self.auth.pack(fill="both", expand=True)

    def login(self, user):
        self.user = user
        self.auth.destroy()
        self.build_shell()

    def logout(self):
        self.show_auth()

    #  shell
    def build_shell(self):
        role = self.user["role"]
        colour = ROLE_COLOUR[role]
        self.place_window(1300, 800, (1150, 660))
        self.shell = tk.Frame(self, bg=C["bg"])
        self.shell.pack(fill="both", expand=True)
        side = tk.Frame(self.shell, bg=C["sidebar"], width=215)
        side.pack(side="left", fill="y")
        side.pack_propagate(False)
        tk.Label(side, text="APEX", font=(FONT, 18, "bold"), bg=C["sidebar"], fg="white"
                 ).pack(anchor="w", padx=22, pady=(24, 0))
        tk.Label(side, text=SUBTITLE[role], font=(FONT, 9), bg=C["sidebar"], fg="#94a3b8"
                 ).pack(anchor="w", padx=22, pady=(0, 22))

        foot = tk.Frame(side, bg=C["sidebar"])
        foot.pack(side="bottom", fill="x", padx=18, pady=18)
        initials = "".join(p[0] for p in self.user["full_name"].split()[:2]).upper()
        row = tk.Frame(foot, bg=C["sidebar"])
        row.pack(fill="x")
        tk.Label(row, text=initials, font=(FONT, 11, "bold"), bg=colour, fg="white", width=3,
                 pady=6).pack(side="left")
        who = tk.Frame(row, bg=C["sidebar"])
        who.pack(side="left", padx=10)
        tk.Label(who, text=self.user["full_name"][:18], font=(FONT, 10, "bold"), bg=C["sidebar"],
                 fg="white").pack(anchor="w")
        tk.Label(who, text=ROLE_LABEL[role], font=(FONT, 9), bg=C["sidebar"], fg="#94a3b8"
                 ).pack(anchor="w")
        FlatButton(foot, "Log out", self.logout, bg=C["sidebar_hover"], hover="#475569", pady=6
                   ).pack(fill="x", pady=(12, 0))

        content = tk.Frame(self.shell, bg=C["bg"])
        content.pack(side="left", fill="both", expand=True, padx=26, pady=22)
        self.pages, self.nav = {}, {}
        for i, (name, factory) in enumerate(PAGES[role], 1):
            self.pages[name] = factory(content, self)
            b = tk.Label(side, text=f"   {name}", anchor="w", font=(FONT, 11, "bold"),
                         bg=C["sidebar"], fg="#cbd5e1", cursor="hand2", pady=11)
            b.pack(fill="x", padx=10, pady=2)
            b.bind("<Button-1>", lambda e, n=name: self.show(n))
            b.bind("<Enter>", lambda e, n=name: self.hover(n, True))
            b.bind("<Leave>", lambda e, n=name: self.hover(n, False))
            self.nav[name] = b
            self.bind(f"<Control-Key-{i}>", lambda e, n=name: self.show(n))
        self.current = None
        self.show("Dashboard")

    def hover(self, name, on):
        if name != self.current:
            self.nav[name].config(bg=C["sidebar_hover"] if on else C["sidebar"])

    def show(self, name, **kw):
        if name not in self.pages:                
            return
        if self.current:
            self.pages[self.current].pack_forget()
            self.nav[self.current].config(bg=C["sidebar"], fg="#cbd5e1")
        self.current = name
        self.nav[name].config(bg=ROLE_COLOUR[self.user["role"]], fg="white")
        page = self.pages[name]
        page.pack(fill="both", expand=True)
        if kw and hasattr(page, "apply"):
            page.apply(**kw)
        if hasattr(page, "load_products"):
            page.load_products()
        if hasattr(page, "refresh"):
            page.refresh()


if __name__ == "__main__":
    App().mainloop()
