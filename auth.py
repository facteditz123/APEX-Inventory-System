"""Login / sign-up screen for Customers, Salespeople and Admins."""
import hmac
import re
import tkinter as tk
from tkinter import ttk

import config
from database import STATES
from ui import C, FONT, ROLE_COLOUR, Card, FlatButton, Segmented


class AuthScreen(tk.Frame):
    ROLES = {"Customer": "customer", "Salesperson": "salesperson", "Admin": "admin"}
    LABELS = {v: k for k, v in ROLES.items()}
    BLURB = {"customer": "Browse products, order online and pick up from your nearest warehouse.",
             "salesperson": "Run the point of sale and monitor orders.",
             "admin": "Manage inventory, warehouses, staff and every order."}

    def __init__(self, parent, app):
        super().__init__(parent, bg=C["bg"])
        self.app = app
        self.v = {k: tk.StringVar() for k in ("name", "user", "phone", "state", "pw", "pw2", "code")}

        # ---- brand panel
        left = tk.Frame(self, bg=C["sidebar"], width=400)
        left.pack(side="left", fill="y")
        left.pack_propagate(False)
        tk.Label(left, text="APEX", font=(FONT, 32, "bold"), bg=C["sidebar"], fg="white"
                 ).pack(anchor="w", padx=40, pady=(80, 0))
        tk.Label(left, text="Inventory  •  Point of sale  •  Orders", font=(FONT, 11),
                 bg=C["sidebar"], fg="#94a3b8").pack(anchor="w", padx=40, pady=(0, 40))
        for t in ("Live stock control ", "Point of sale ",
                  "Order tracking across all 37 states",
                  "Pick up from your nearest warehouse"):
            tk.Label(left, text="•  " + t, font=(FONT, 11), bg=C["sidebar"], fg="#e2e8f0",
                     anchor="w").pack(anchor="w", padx=40, pady=5)

        # ---- form card
        right = tk.Frame(self, bg=C["bg"])
        right.pack(side="left", fill="both", expand=True)
        card = Card(right)
        card.place(relx=0.5, rely=0.5, anchor="center")
        box = tk.Frame(card, bg=C["card"])
        box.pack(padx=34, pady=22)
        self.title = tk.Label(box, font=(FONT, 19, "bold"), bg=C["card"], fg=C["text"])
        self.title.pack(anchor="w")
        self.sub = tk.Label(box, font=(FONT, 9), bg=C["card"], fg=C["muted"], wraplength=330,
                            justify="left")
        self.sub.pack(anchor="w", pady=(2, 12))
        self.mode = Segmented(box, ["Log in", "Sign up"], command=lambda v: self.layout())
        self.mode.pack(anchor="w")
        tk.Label(box, text="I AM A", font=(FONT, 9, "bold"), bg=C["card"], fg=C["muted"]
                 ).pack(anchor="w", pady=(14, 2))
        self.role = Segmented(box, list(self.ROLES), command=lambda v: self.layout())
        self.role.pack(anchor="w")

        self.form = tk.Frame(box, bg=C["card"])
        self.form.pack(fill="x", pady=(2, 0))
        self.form.columnconfigure((0, 1), weight=1, uniform="f", minsize=165)
        self.fields, self.labels = {}, {}
        spec = [("name", "FULL NAME", False), ("user", "USERNAME", False),
                ("phone", "PHONE (OPTIONAL)", False), ("state", "YOUR STATE", None),
                ("pw", "PASSWORD", True), ("pw2", "CONFIRM", True),
                ("code", "ACCESS CODE", True)]
        for key, label, secret in spec:
            row = tk.Frame(self.form, bg=C["card"])
            self.labels[key] = tk.Label(row, text=label, font=(FONT, 9, "bold"), bg=C["card"],
                                        fg=C["muted"])
            self.labels[key].pack(anchor="w", pady=(8, 2))
            if key == "state":
                w = ttk.Combobox(row, textvariable=self.v[key], values=STATES, state="readonly",
                                 style="Modern.TCombobox", width=14)
            else:
                w = ttk.Entry(row, textvariable=self.v[key], width=14, style="Modern.TEntry",
                              show="•" if secret else "")
            w.pack(fill="x")
            w.bind("<Return>", self.submit)
            self.fields[key] = (row, w)

        self.show_pw = tk.BooleanVar()
        tk.Checkbutton(box, text="Show password", variable=self.show_pw, command=self.toggle_pw,
                       bg=C["card"], fg=C["muted"], activebackground=C["card"], bd=0,
                       highlightthickness=0, font=(FONT, 9), cursor="hand2"
                       ).pack(anchor="w", pady=(8, 0))
        self.msg = tk.Label(box, text="", font=(FONT, 9), bg=C["card"], wraplength=330,
                            justify="left")
        self.msg.pack(anchor="w", pady=(6, 0))
        self.btn = FlatButton(box, "Log in", self.submit, pady=10, font_size=11)
        self.btn.pack(fill="x", pady=(8, 0))
        self.layout()

    # ------------------------------------------------------------------ helpers
    def toggle_pw(self):
        ch = "" if self.show_pw.get() else "•"
        for k in ("pw", "pw2", "code"):
            self.fields[k][1].config(show=ch)

    def err(self, text, ok=False):
        self.msg.config(text=text, fg=C["success"] if ok else C["danger"])

    def layout(self):
        signup = self.mode.get() == "Sign up"
        role = self.ROLES[self.role.get()]
        rows = [["user"], ["pw"]]
        if signup:
            rows = [["name", "user"], ["phone", "state"] if role == "customer" else ["phone"],
                    ["pw", "pw2"]] + ([] if role == "customer" else [["code"]])
        for row, _ in self.fields.values():
            row.grid_forget()
        for r, keys in enumerate(rows):
            for c, k in enumerate(keys):
                self.fields[k][0].grid(row=r, column=c, columnspan=2 if len(keys) == 1 else 1,
                                       sticky="ew", padx=(0 if c == 0 else 6, 0))
        self.labels["code"].config(
            text="ADMIN ACCESS CODE" if role == "admin" else "STAFF ACCESS CODE")
        self.title.config(text="Create your account" if signup else "Welcome back")
        self.sub.config(text=self.BLURB[role])
        colour = ROLE_COLOUR[role]
        self.btn.config(text="Create account" if signup else "Log in")
        self.btn.recolor(colour, colour)
        self.msg.config(text="")

    def submit(self, _event=None):
        (self.signup if self.mode.get() == "Sign up" else self.login)()

    # ------------------------------------------------------------------- actions
    def login(self):
        user = self.app.db.authenticate(self.v["user"].get(), self.v["pw"].get())
        if not user:
            return self.err("Wrong username or password.")
        want = self.ROLES[self.role.get()]
        if user["role"] != want:
            return self.err(f"This is a {self.LABELS[user['role']]} account - "
                            f"choose '{self.LABELS[user['role']]}' above to log in.")
        self.v["pw"].set("")
        self.app.login(user)

    def signup(self):
        role = self.ROLES[self.role.get()]
        name, user = self.v["name"].get().strip(), self.v["user"].get().strip().lower()
        pw, pw2 = self.v["pw"].get(), self.v["pw2"].get()
        if len(name) < 2:
            return self.err("Please enter your full name.")
        if not re.fullmatch(r"[a-z0-9_.]{3,20}", user):
            return self.err("Username must be 3-20 letters, numbers, '_' or '.'.")
        if len(pw) < 4:
            return self.err("Password must be at least 4 characters.")
        if pw != pw2:
            return self.err("The two passwords don't match.")
        if role != "customer":
            expected = config.ADMIN_CODE if role == "admin" else config.STAFF_CODE
            if not hmac.compare_digest(self.v["code"].get().strip(), expected):
                return self.err("That access code is not valid.")
        state = self.v["state"].get() if role == "customer" else ""
        try:
            self.app.db.create_user(user, name, pw, role, self.v["phone"].get(), state)
        except ValueError as e:
            return self.err(str(e))
        for k in ("name", "pw", "pw2", "code", "phone"):
            self.v[k].set("")
        self.mode.set("Log in")
        self.layout()
        self.v["user"].set(user)
        self.err("Account created - log in to continue.", ok=True)
