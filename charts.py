import math
import tkinter as tk

from ui import C, FONT


class HBarChart(tk.Canvas):
    """Horizontal bars: [(label, value)] largest first."""

    def __init__(self, parent, colour, fmt, rows=5):
        super().__init__(parent, bg=C["card"], highlightthickness=0, height=rows * 34 + 6)
        self.colour, self.fmt, self.rows, self.data = colour, fmt, rows, []
        self.bind("<Configure>", lambda e: self.draw())

    def set_data(self, data):
        self.data = data[: self.rows]
        self.draw()

    def draw(self):
        self.delete("all")
        w = self.winfo_width()
        if w < 60:
            return
        if not self.data:
            self.create_text(w / 2, 70, text="No sales in this period yet", fill=C["muted"],
                             font=(FONT, 10))
            return
        label_w, val_w = 125, 100
        room = max(w - label_w - val_w, 20)
        top = max(v for _, v in self.data) or 1
        for i, (label, v) in enumerate(self.data):
            y = 6 + i * 34
            text = label if len(label) <= 17 else label[:16] + "…"
            self.create_text(0, y + 14, text=text, anchor="w", fill=C["text"], font=(FONT, 10))
            bw = max(int(room * v / top), 3)
            self.create_rectangle(label_w, y + 4, label_w + bw, y + 24, fill=self.colour, width=0)
            self.create_text(label_w + bw + 8, y + 14, text=self.fmt(v), anchor="w",
                             fill=C["muted"], font=(FONT, 9, "bold"))


class VBarChart(tk.Canvas):
    """Vertical bars over time: [(label, value)] in chronological order."""

    def __init__(self, parent, colour, fmt, height=176):
        super().__init__(parent, bg=C["card"], highlightthickness=0, height=height)
        self.colour, self.fmt, self.data = colour, fmt, []
        self.bind("<Configure>", lambda e: self.draw())

    def set_data(self, data):
        self.data = data
        self.draw()

    def draw(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 60:
            return
        if not self.data or max(v for _, v in self.data) <= 0:
            self.create_text(w / 2, h / 2 - 10, text="No sales in this period yet",
                             fill=C["muted"], font=(FONT, 10))
            return
        pl, pr, pt, pb = 6, 6, 20, 24
        n = len(self.data)
        slot = (w - pl - pr) / n
        bw = min(slot * 0.7, 38)
        top = max(v for _, v in self.data)
        base = h - pb
        step = max(1, math.ceil(n / max(int((w - pl - pr) / 52), 1)))
        peak = max(range(n), key=lambda i: self.data[i][1])
        for i, (label, v) in enumerate(self.data):
            x0 = pl + i * slot + (slot - bw) / 2
            bh = (base - pt) * v / top
            if v > 0:
                self.create_rectangle(x0, base - bh, x0 + bw, base, fill=self.colour, width=0)
            if v > 0 and (slot >= 52 or i == peak):
                self.create_text(min(max(x0 + bw / 2, 30), w - 30), base - bh - 8, text=self.fmt(v),
                                 fill=C["muted"], font=(FONT, 8, "bold"))
            if i % step == 0:
                self.create_text(x0 + bw / 2, base + 12, text=label, fill=C["muted"], font=(FONT, 8))
        self.create_line(pl, base, w - pr, base, fill=C["border"])
