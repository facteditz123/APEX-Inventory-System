import os
import tkinter as tk
from datetime import datetime
from tkinter import ttk

from config import CURRENCY
from database import to_float, to_int  
C = {
    "bg": "#f1f5f9", "card": "#ffffff", "sidebar": "#1e293b", "sidebar_hover": "#334155",
    "text": "#0f172a", "muted": "#64748b", "border": "#e2e8f0", "seg": "#e8edf3",
    "accent": "#4f46e5", "accent_dark": "#4338ca", "danger": "#dc2626",
    "danger_dark": "#b91c1c", "success": "#16a34a", "success_dark": "#15803d",
    "warn": "#d97706", "row_alt": "#f8fafc", "low_bg": "#fef3c7", "out_bg": "#fee2e2",
}
FONT = "Segoe UI" if os.name == "nt" else "Helvetica"

ROLE_LABEL = {"admin": "Admin", "salesperson": "Salesperson", "customer": "Customer"}
ROLE_COLOUR = {"admin": "#4f46e5", "salesperson": "#0d9488", "customer": "#ea580c"}

# order status
STATUS_STYLE = {
    "In Warehouse": ("st_wh", "#fef3c7", "#92400e"),
    "In Transit": ("st_transit", "#dbeafe", "#1e40af"),
    "Delivered": ("st_done", "#dcfce7", "#166534"),
    "Cancelled": ("st_cancel", "#f1f5f9", "#64748b"),
}


def money(value):
    try:
        return f"{CURRENCY}{float(value):,.2f}"
    except (TypeError, ValueError):
        return f"{CURRENCY}0.00"


def greeting():
    h = datetime.now().hour
    return "Good morning" if h < 12 else "Good afternoon" if h < 17 else "Good evening"


def center_window(win, parent):
    win.update_idletasks()
    top = parent.winfo_toplevel()
    x = top.winfo_rootx() + (top.winfo_width() - win.winfo_width()) // 2
    y = top.winfo_rooty() + (top.winfo_height() - win.winfo_height()) // 3
    win.geometry(f"+{max(x, 0)}+{max(y, 0)}")


class FlatButton(tk.Label):
    """A flat coloured button that looks the same on every OS."""

    def __init__(self, parent, text, command, bg=None, fg="white", hover=None,
                 pady=8, font_size=10, **kw):
        self._bg = bg or C["accent"]
        self._hover = hover or C["accent_dark"]
        self._cmd = command
        super().__init__(parent, text=text, bg=self._bg, fg=fg, cursor="hand2",
                         font=(FONT, font_size, "bold"), padx=14, pady=pady, **kw)
        self.bind("<Enter>", lambda e: self.config(bg=self._hover))
        self.bind("<Leave>", lambda e: self.config(bg=self._bg))
        self.bind("<Button-1>", lambda e: self._cmd())

    def recolor(self, bg, hover):
        self._bg, self._hover = bg, hover
        self.config(bg=bg)


class Card(tk.Frame):
    def __init__(self, parent, **kw):
        super().__init__(parent, bg=C["card"], highlightthickness=1,
                         highlightbackground=C["border"], highlightcolor=C["border"], **kw)


class Segmented(tk.Frame):
    """Pill-shaped tab / option selector."""

    def __init__(self, parent, options, command=None, value=None, accent=None):
        super().__init__(parent, bg=C["seg"], padx=2, pady=2)
        self.value, self.command = value or options[0], command
        self.accent = accent or C["accent"]
        self.buttons = {}
        for o in options:
            b = tk.Label(self, text=o, font=(FONT, 9, "bold"), padx=12, pady=6, cursor="hand2")
            b.pack(side="left", padx=1)
            b.bind("<Button-1>", lambda e, o=o: self.set(o, fire=True))
            self.buttons[o] = b
        self.set(self.value)

    def get(self):
        return self.value

    def set(self, value, fire=False):
        self.value = value
        for o, b in self.buttons.items():
            on = o == value
            b.config(bg=C["card"] if on else C["seg"], fg=self.accent if on else C["muted"])
        if fire and self.command:
            self.command(value)


def make_tree(parent, columns, widths, anchors=None, height=12):
    """Styled Treeview + scrollbar. columns = [(id, heading)]. Returns (frame, tree)."""
    frame = tk.Frame(parent, bg=C["card"])
    tree = ttk.Treeview(frame, columns=[c[0] for c in columns], show="headings",
                        height=height, selectmode="browse", style="Modern.Treeview")
    for (cid, head), w in zip(columns, widths):
        anchor = (anchors or {}).get(cid, "w")
        tree.heading(cid, text=head, anchor=anchor)
        tree.column(cid, width=w, minwidth=40, anchor=anchor, stretch=True)
    sb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=sb.set)
    tree.pack(side="left", fill="both", expand=True)
    sb.pack(side="right", fill="y")
    tree.tag_configure("odd", background=C["row_alt"])
    tree.tag_configure("low", background=C["low_bg"], foreground="#92400e")
    tree.tag_configure("out", background=C["out_bg"], foreground="#991b1b")
    for tag, bg, fg in STATUS_STYLE.values():
        tree.tag_configure(tag, background=bg, foreground=fg)
    return frame, tree


def page_header(parent, title, subtitle):
    head = tk.Frame(parent, bg=C["bg"])
    tk.Label(head, text=title, font=(FONT, 20, "bold"), bg=C["bg"], fg=C["text"]).pack(anchor="w")
    tk.Label(head, text=subtitle, font=(FONT, 10), bg=C["bg"], fg=C["muted"]).pack(anchor="w")
    return head


def labeled_entry(parent, label, var, row, width=28, secret=False):
    tk.Label(parent, text=label, font=(FONT, 9, "bold"), bg=C["card"], fg=C["muted"]
             ).grid(row=row * 2, column=0, sticky="w", pady=(10, 2))
    e = ttk.Entry(parent, textvariable=var, width=width, style="Modern.TEntry",
                  show="•" if secret else "")
    e.grid(row=row * 2 + 1, column=0, sticky="ew")
    return e


def stat_cards(parent, specs):
    """Row of KPI cards. specs = [(key, label, colour)]. Returns (frame, {key: Label})."""
    frame, labels = tk.Frame(parent, bg=C["bg"]), {}
    for i, (key, label, colour) in enumerate(specs):
        frame.columnconfigure(i, weight=1, uniform="stat")
        card = Card(frame)
        card.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 10, 0))
        tk.Frame(card, bg=colour, height=4).pack(fill="x")
        tk.Label(card, text=label, font=(FONT, 9, "bold"), bg=C["card"], fg=C["muted"]
                 ).pack(anchor="w", padx=14, pady=(10, 0))
        labels[key] = tk.Label(card, text="-", font=(FONT, 17, "bold"), bg=C["card"], fg=C["text"])
        labels[key].pack(anchor="w", padx=14, pady=(2, 12))
    return frame, labels


def banner(parent, colour, title, subtitle, action=None):
    f = tk.Frame(parent, bg=colour)
    inner = tk.Frame(f, bg=colour)
    inner.pack(side="left", padx=22, pady=16)
    tk.Label(inner, text=title, font=(FONT, 18, "bold"), bg=colour, fg="white").pack(anchor="w")
    tk.Label(inner, text=subtitle, font=(FONT, 10), bg=colour, fg="#f1f5f9").pack(anchor="w")
    if action:
        FlatButton(f, action[0], action[1], bg="white", fg=colour, hover="#f1f5f9"
                   ).pack(side="right", padx=22)
    return f


def setup_styles(root):
    s = ttk.Style(root)
    s.theme_use("clam")
    root.option_add("*TCombobox*Listbox.font", (FONT, 10))
    s.configure("Modern.Treeview", background=C["card"], fieldbackground=C["card"],
                foreground=C["text"], rowheight=32, borderwidth=0, font=(FONT, 10))
    s.configure("Modern.Treeview.Heading", background=C["bg"], foreground=C["muted"],
                font=(FONT, 9, "bold"), relief="flat", padding=(8, 8))
    s.map("Modern.Treeview.Heading", background=[("active", C["border"])])
    s.map("Modern.Treeview", background=[("selected", C["accent"])],
          foreground=[("selected", "white")])
    s.layout("Modern.Treeview", [("Treeview.treearea", {"sticky": "nswe"})])
    for w in ("TEntry", "TSpinbox", "TCombobox"):
        s.configure(f"Modern.{w}", padding=7, fieldbackground="white", bordercolor=C["border"],
                    lightcolor=C["border"], darkcolor=C["border"], font=(FONT, 10))
        s.map(f"Modern.{w}", bordercolor=[("focus", C["accent"])],
              lightcolor=[("focus", C["accent"])], darkcolor=[("focus", C["accent"])])
    s.map("Modern.TCombobox", fieldbackground=[("readonly", "white")],
          background=[("readonly", "white")], foreground=[("readonly", C["text"])],
          selectbackground=[("readonly", "white")], selectforeground=[("readonly", C["text"])])
    s.configure("Vertical.TScrollbar", background=C["border"], troughcolor=C["card"],
                bordercolor=C["card"], arrowsize=0, relief="flat")
