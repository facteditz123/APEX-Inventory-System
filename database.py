import hashlib
import hmac
import math
import secrets
import sqlite3
from datetime import datetime

ORDER_STATUSES = ["In Warehouse", "In Transit", "Delivered", "Cancelled"]

# (state, warehouse city, latitude, longitude) - one warehouse per state + FCT
NIGERIA = [
    ("Abia", "Umuahia", 5.5320, 7.4860), ("Adamawa", "Yola", 9.2035, 12.4954),
    ("Akwa Ibom", "Uyo", 5.0377, 7.9128), ("Anambra", "Awka", 6.2104, 7.0719),
    ("Bauchi", "Bauchi", 10.3158, 9.8442), ("Bayelsa", "Yenagoa", 4.9267, 6.2676),
    ("Benue", "Makurdi", 7.7337, 8.5121), ("Borno", "Maiduguri", 11.8333, 13.1500),
    ("Cross River", "Calabar", 4.9757, 8.3417), ("Delta", "Asaba", 6.1980, 6.7340),
    ("Ebonyi", "Abakaliki", 6.3249, 8.1137), ("Edo", "Benin City", 6.3350, 5.6037),
    ("Ekiti", "Ado-Ekiti", 7.6211, 5.2214), ("Enugu", "Enugu", 6.4584, 7.5464),
    ("FCT", "Abuja", 9.0765, 7.3986), ("Gombe", "Gombe", 10.2897, 11.1673),
    ("Imo", "Owerri", 5.4850, 7.0350), ("Jigawa", "Dutse", 11.7564, 9.3388),
    ("Kaduna", "Kaduna", 10.5105, 7.4165), ("Kano", "Kano", 12.0022, 8.5920),
    ("Katsina", "Katsina", 12.9908, 7.6018), ("Kebbi", "Birnin Kebbi", 12.4539, 4.1975),
    ("Kogi", "Lokoja", 7.8023, 6.7333), ("Kwara", "Ilorin", 8.4966, 4.5421),
    ("Lagos", "Ikeja", 6.6018, 3.3515), ("Nasarawa", "Lafia", 8.4939, 8.5153),
    ("Niger", "Minna", 9.6139, 6.5569), ("Ogun", "Abeokuta", 7.1475, 3.3619),
    ("Ondo", "Akure", 7.2571, 5.2058), ("Osun", "Osogbo", 7.7827, 4.5418),
    ("Oyo", "Ibadan", 7.3775, 3.9470), ("Plateau", "Jos", 9.8965, 8.8583),
    ("Rivers", "Port Harcourt", 4.8156, 7.0498), ("Sokoto", "Sokoto", 13.0059, 5.2476),
    ("Taraba", "Jalingo", 8.8937, 11.3596), ("Yobe", "Damaturu", 11.7470, 11.9608),
    ("Zamfara", "Gusau", 12.1704, 6.6641),
]
STATES = [n[0] for n in NIGERIA]


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def to_float(value, default=0.0):
    try:
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return default


def to_int(value, default=0):
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return default


def hash_password(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"),
                                 bytes.fromhex(salt), 150_000).hex()
    return salt, digest


def km_between(lat1, lng1, lat2, lng2):
    """Great-circle distance in kilometres (haversine)."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lng2 - lng1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371.0 * math.asin(math.sqrt(h))


class Database:
    NEXT = {"In Warehouse": ("In Transit", "Delivered", "Cancelled"),
            "In Transit": ("Delivered",), "Delivered": (), "Cancelled": ()}

    def __init__(self, path):
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.listeners = []         
        c = self.conn
        c.executescript("""
        CREATE TABLE IF NOT EXISTS stock(Product_Id varchar(100), Product_Name varchar(100),
            Sell_Price varchar(100), Quantity varchar(100));
        CREATE TABLE IF NOT EXISTS sales(id INTEGER PRIMARY KEY AUTOINCREMENT, created TEXT,
            subtotal REAL, discount REAL, total REAL);
        CREATE TABLE IF NOT EXISTS sale_items(sale_id INTEGER, product_id TEXT, name TEXT,
            price REAL, qty INTEGER, line_total REAL);
        CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE, full_name TEXT, role TEXT, phone TEXT, state TEXT,
            salt TEXT, pw_hash TEXT, created TEXT);
        CREATE TABLE IF NOT EXISTS warehouses(id INTEGER PRIMARY KEY AUTOINCREMENT,
            state TEXT UNIQUE, name TEXT, city TEXT, address TEXT, phone TEXT, lat REAL, lng REAL);
        CREATE TABLE IF NOT EXISTS orders(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
            customer TEXT, phone TEXT, state TEXT, address TEXT, warehouse_id INTEGER,
            status TEXT, total REAL, created TEXT, updated TEXT);
        CREATE TABLE IF NOT EXISTS order_items(order_id INTEGER, product_id TEXT, name TEXT,
            price REAL, qty INTEGER);
        CREATE TABLE IF NOT EXISTS order_events(order_id INTEGER, status TEXT, at TEXT, actor TEXT);
        """)
        cols = [r["name"] for r in c.execute("PRAGMA table_info(sales)")]
        if "cashier_id" not in cols:
            c.execute("ALTER TABLE sales ADD COLUMN cashier_id INTEGER")
        if "cashier" not in cols:
            c.execute("ALTER TABLE sales ADD COLUMN cashier TEXT")
        # One flat table of every sale line (POS + online) - used by Analytics, Excel and Power BI.
        # POS discounts are shared out across the lines so revenue is the real amount paid.
        c.execute("""
        CREATE VIEW IF NOT EXISTS sales_facts AS
        SELECT 'POS (in-store)' AS channel, s.created AS sold_at, substr(s.created,1,10) AS sale_date,
               s.id AS reference, si.product_id AS product_id, si.name AS product, si.qty AS units,
               ROUND(CASE WHEN s.subtotal > 0 THEN si.line_total * s.total / s.subtotal
                          ELSE si.line_total END, 2) AS revenue,
               'In-store' AS location, COALESCE(s.cashier,'') AS salesperson, '' AS customer
        FROM sale_items si JOIN sales s ON s.id = si.sale_id
        UNION ALL
        SELECT 'Online order', o.created, substr(o.created,1,10), o.id, oi.product_id, oi.name, oi.qty,
               ROUND(oi.price * oi.qty, 2), COALESCE(o.state,''), '', COALESCE(o.customer,'')
        FROM order_items oi JOIN orders o ON o.id = oi.order_id WHERE o.status <> 'Cancelled'""")
        if not c.execute("SELECT 1 FROM warehouses LIMIT 1").fetchone():
            for state, city, lat, lng in NIGERIA:
                c.execute("INSERT INTO warehouses (state,name,city,address,phone,lat,lng) "
                          "VALUES (?,?,?,?,?,?,?)",
                          (state, f"{state} Warehouse", city,
                           f"Warehouse Road, {city}, {state}", "", lat, lng))
        c.commit()

    def _notify(self):
        for fn in self.listeners:
            fn()

    def sales_facts(self, since=None):
        """Every sold line (POS + online, cancelled orders excluded). since = 'YYYY-MM-DD' or None."""
        q, args = "SELECT * FROM sales_facts", []
        if since:
            q += " WHERE sale_date >= ?"
            args.append(since)
        return self.conn.execute(q + " ORDER BY sold_at", args).fetchall()

    #  users
    def create_user(self, username, full_name, password, role, phone="", state=""):
        username = username.strip().lower()
        if self.conn.execute("SELECT 1 FROM users WHERE username=?", (username,)).fetchone():
            raise ValueError("That username is already taken.")
        salt, digest = hash_password(password)
        cur = self.conn.execute(
            "INSERT INTO users (username,full_name,role,phone,state,salt,pw_hash,created) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (username, full_name.strip(), role, phone.strip(), state, salt, digest, now()))
        self.conn.commit()
        return cur.lastrowid

    def authenticate(self, username, password):
        r = self.conn.execute("SELECT * FROM users WHERE username=?",
                              (username.strip().lower(),)).fetchone()
        if not r:
            return None
        _, digest = hash_password(password, r["salt"])
        return dict(r) if hmac.compare_digest(digest, r["pw_hash"]) else None

    def users(self):
        return self.conn.execute("SELECT * FROM users ORDER BY role, full_name").fetchall()

    def delete_user(self, uid):
        self.conn.execute("DELETE FROM users WHERE id=?", (uid,))
        self.conn.commit()

    def update_user_location(self, uid, state, phone):
        self.conn.execute("UPDATE users SET state=?, phone=? WHERE id=?", (state, phone, uid))
        self.conn.commit()

    #  products
    @staticmethod
    def _p(r):
        return (r["Product_Id"], r["Product_Name"], to_float(r["Sell_Price"]), to_int(r["Quantity"]))

    def products(self, search=""):
        items = [self._p(r) for r in self.conn.execute("SELECT * FROM stock")]
        s = search.strip().lower()
        if s:
            items = [i for i in items if s in str(i[0]).lower() or s in str(i[1]).lower()]
        return items

    def product(self, pid):
        r = self.conn.execute("SELECT * FROM stock WHERE Product_Id=?", (pid,)).fetchone()
        return self._p(r) if r else None

    def add_product(self, pid, name, price, qty):
        self.conn.execute("INSERT INTO stock (Product_Id,Product_Name,Sell_Price,Quantity) "
                          "VALUES (?,?,?,?)", (pid, name, price, qty))
        self.conn.commit()
        self._notify()

    def update_product(self, old_pid, pid, name, price, qty):
        self.conn.execute("UPDATE stock SET Product_Id=?,Product_Name=?,Sell_Price=?,Quantity=? "
                          "WHERE Product_Id=?", (pid, name, price, qty, old_pid))
        self.conn.commit()
        self._notify()

    def delete_product(self, pid):
        self.conn.execute("DELETE FROM stock WHERE Product_Id=?", (pid,))
        self.conn.commit()
        self._notify()

    def _check_stock(self, cur, lines):
        for l in lines:
            row = cur.execute("SELECT Quantity FROM stock WHERE Product_Id=?", (l["id"],)).fetchone()
            have = to_int(row["Quantity"]) if row else 0
            if have < l["qty"]:
                raise ValueError(f"Not enough stock for {l['name']} "
                                 f"(available {have}, requested {l['qty']}).")

    #  POS sales
    def checkout(self, cart, discount_pct, cashier):
        cur = self.conn.cursor()
        try:
            self._check_stock(cur, cart)
            subtotal = sum(l["price"] * l["qty"] for l in cart)
            discount = subtotal * discount_pct / 100.0
            total = subtotal - discount
            cur.execute("INSERT INTO sales (created,subtotal,discount,total,cashier_id,cashier) "
                        "VALUES (?,?,?,?,?,?)",
                        (now(), subtotal, discount, total, cashier["id"], cashier["full_name"]))
            sale_id = cur.lastrowid
            for l in cart:
                cur.execute("UPDATE stock SET Quantity = CAST(Quantity AS INTEGER) - ? "
                            "WHERE Product_Id=?", (l["qty"], l["id"]))
                cur.execute("INSERT INTO sale_items VALUES (?,?,?,?,?,?)",
                            (sale_id, l["id"], l["name"], l["price"], l["qty"],
                             l["price"] * l["qty"]))
            self.conn.commit()
            self._notify()
            return sale_id, subtotal, discount, total
        except Exception:
            self.conn.rollback()
            raise

    def recent_sales(self, limit=None, cashier_id=None):
        q, args = "SELECT * FROM sales", []
        if cashier_id is not None:
            q += " WHERE cashier_id=?"
            args.append(cashier_id)
        q += " ORDER BY id DESC" + (f" LIMIT {int(limit)}" if limit else "")
        return self.conn.execute(q, args).fetchall()

    def sale_items(self, sale_id):
        return self.conn.execute("SELECT * FROM sale_items WHERE sale_id=?", (sale_id,)).fetchall()

    def sales_stats(self, cashier_id=None):
        w, args = "", []
        if cashier_id is not None:
            w, args = " AND cashier_id=?", [cashier_id]
        today = datetime.now().strftime("%Y-%m-%d") + "%"
        t = self.conn.execute("SELECT COALESCE(SUM(total),0) t, COUNT(*) n FROM sales "
                              "WHERE created LIKE ?" + w, [today] + args).fetchone()
        a = self.conn.execute("SELECT COALESCE(SUM(total),0) t, COUNT(*) n FROM sales WHERE 1=1"
                              + w, args).fetchone()
        return {"today_total": t["t"], "today_n": t["n"], "all_total": a["t"], "all_n": a["n"]}

    #  warehouses
    def warehouses(self):
        return self.conn.execute("SELECT * FROM warehouses ORDER BY state").fetchall()

    def warehouse(self, wid):
        return self.conn.execute("SELECT * FROM warehouses WHERE id=?", (wid,)).fetchone()

    def nearest_warehouses(self, state, n=3):
        """[(warehouse_row, km)] closest first, measured from the given state."""
        origin = next((w for w in NIGERIA if w[0] == state), None)
        rows = self.warehouses()
        if not origin:
            return [(r, None) for r in rows[:n]]
        scored = [(r, km_between(origin[2], origin[3], r["lat"], r["lng"])) for r in rows]
        return sorted(scored, key=lambda t: t[1])[:n]

    def update_warehouse(self, wid, name, address, phone):
        self.conn.execute("UPDATE warehouses SET name=?,address=?,phone=? WHERE id=?",
                          (name, address, phone, wid))
        self.conn.commit()

    def warehouse_summary(self):
        return self.conn.execute("""
            SELECT w.*,
              COALESCE(SUM(CASE WHEN o.status='In Warehouse' THEN 1 ELSE 0 END),0) AS n_wh,
              COALESCE(SUM(CASE WHEN o.status='In Transit' THEN 1 ELSE 0 END),0) AS n_tr,
              COALESCE(SUM(CASE WHEN o.status='Delivered' THEN 1 ELSE 0 END),0) AS n_dl
            FROM warehouses w LEFT JOIN orders o ON o.warehouse_id = w.id
            GROUP BY w.id ORDER BY w.state""").fetchall()

    #  orders
    def place_order(self, user, lines, state, address, phone, wid):
        cur = self.conn.cursor()
        try:
            self._check_stock(cur, lines)
            total = sum(l["price"] * l["qty"] for l in lines)
            stamp = now()
            cur.execute("INSERT INTO orders (user_id,customer,phone,state,address,warehouse_id,"
                        "status,total,created,updated) VALUES (?,?,?,?,?,?,?,?,?,?)",
                        (user["id"], user["full_name"], phone, state, address, wid,
                         "In Warehouse", total, stamp, stamp))
            oid = cur.lastrowid
            for l in lines:
                cur.execute("UPDATE stock SET Quantity = CAST(Quantity AS INTEGER) - ? "
                            "WHERE Product_Id=?", (l["qty"], l["id"]))
                cur.execute("INSERT INTO order_items VALUES (?,?,?,?,?)",
                            (oid, l["id"], l["name"], l["price"], l["qty"]))
            cur.execute("INSERT INTO order_events VALUES (?,?,?,?)",
                        (oid, "In Warehouse", stamp, user["full_name"]))
            self.conn.commit()
            self._notify()
            return oid
        except Exception:
            self.conn.rollback()
            raise

    def orders(self, wid=None, status=None, user_id=None, search=""):
        q = """SELECT o.*, w.name AS wh_name, w.state AS wh_state, w.city AS wh_city,
               (SELECT group_concat(name || ' x' || qty, ', ') FROM order_items
                 WHERE order_id=o.id) AS items
               FROM orders o LEFT JOIN warehouses w ON w.id=o.warehouse_id WHERE 1=1"""
        args = []
        for col, val in (("o.warehouse_id", wid), ("o.status", status), ("o.user_id", user_id)):
            if val is not None:
                q += f" AND {col}=?"
                args.append(val)
        rows = self.conn.execute(q + " ORDER BY o.id DESC", args).fetchall()
        s = search.strip().lower()
        if s:
            rows = [r for r in rows if s in str(r["id"]) or s in (r["customer"] or "").lower()
                    or s in (r["items"] or "").lower()]
        return rows

    def order(self, oid):
        return self.conn.execute(
            "SELECT o.*, w.name AS wh_name, w.state AS wh_state, w.address AS wh_address, "
            "w.phone AS wh_phone FROM orders o LEFT JOIN warehouses w ON w.id=o.warehouse_id "
            "WHERE o.id=?", (oid,)).fetchone()

    def order_items(self, oid):
        return self.conn.execute("SELECT * FROM order_items WHERE order_id=?", (oid,)).fetchall()

    def order_events(self, oid):
        return self.conn.execute("SELECT * FROM order_events WHERE order_id=? ORDER BY rowid",
                                 (oid,)).fetchall()

    def order_counts(self, wid=None, user_id=None):
        counts = {s: 0 for s in ORDER_STATUSES}
        q, args = "SELECT status, COUNT(*) n FROM orders WHERE 1=1", []
        if wid is not None:
            q += " AND warehouse_id=?"
            args.append(wid)
        if user_id is not None:
            q += " AND user_id=?"
            args.append(user_id)
        for r in self.conn.execute(q + " GROUP BY status", args):
            counts[r["status"]] = r["n"]
        return counts

    def set_status(self, oid, status, actor):
        o = self.order(oid)
        if not o:
            raise ValueError("Order not found.")
        if status not in self.NEXT.get(o["status"], ()):
            raise ValueError(f"An order that is '{o['status']}' can't be changed to '{status}'.")
        cur = self.conn.cursor()
        if status == "Cancelled":                       
            for it in self.order_items(oid):
                cur.execute("UPDATE stock SET Quantity = CAST(Quantity AS INTEGER) + ? "
                            "WHERE Product_Id=?", (it["qty"], it["product_id"]))
        cur.execute("UPDATE orders SET status=?, updated=? WHERE id=?", (status, now(), oid))
        cur.execute("INSERT INTO order_events VALUES (?,?,?,?)", (oid, status, now(), actor))
        self.conn.commit()
        self._notify()
