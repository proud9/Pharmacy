import os
import sqlite3
from datetime import datetime
from functools import wraps

from flask import Flask, flash, redirect, render_template, request, session, url_for

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "pharmacy.db")

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY") or os.urandom(32)


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                name TEXT NOT NULL,
                role TEXT DEFAULT 'Staff'
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                sku TEXT UNIQUE NOT NULL,
                unit_price REAL NOT NULL,
                cost_price REAL NOT NULL,
                stock_qty INTEGER NOT NULL DEFAULT 0,
                reorder_level INTEGER NOT NULL DEFAULT 0,
                supplier TEXT,
                expiry_date TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sales (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL,
                quantity INTEGER NOT NULL,
                unit_price REAL NOT NULL,
                total REAL NOT NULL,
                sold_at TEXT DEFAULT CURRENT_TIMESTAMP,
                cashier TEXT,
                FOREIGN KEY(product_id) REFERENCES products(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS inventory_movements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL,
                movement_type TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                note TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(product_id) REFERENCES products(id)
            )
            """
        )

        admin = conn.execute(
            "SELECT id FROM users WHERE username = ?", ("admin",)
        ).fetchone()
        if admin is None:
            conn.execute(
                "INSERT INTO users (username, password, name, role) VALUES (?, ?, ?, ?)",
                ("admin", "admin123", "System Administrator", "Administrator"),
            )

        if conn.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 0:
            products = [
                (
                    "Paracetamol 500mg",
                    "Pain Relief",
                    "PAR-500",
                    260.00,
                    120.00,
                    180,
                    40,
                    "Medline Suppliers",
                    "2027-12-15",
                ),
                (
                    "Amoxicillin 250mg",
                    "Antibiotics",
                    "AMX-250",
                    420.00,
                    210.00,
                    96,
                    25,
                    "Prime Pharma",
                    "2026-11-20",
                ),
                (
                    "Insulin Glargine",
                    "Diabetic Care",
                    "INS-GLA",
                    1500.00,
                    980.00,
                    22,
                    15,
                    "Medicare Ltd",
                    "2027-02-05",
                ),
                (
                    "Vitamin C Tablets",
                    "Supplements",
                    "VIT-C-100",
                    180.00,
                    90.00,
                    68,
                    30,
                    "Biocare Distributors",
                    "2028-04-14",
                ),
                (
                    "Salbutamol Inhaler",
                    "Respiratory",
                    "SAL-001",
                    610.00,
                    330.00,
                    12,
                    10,
                    "Health Bridge",
                    "2026-10-10",
                ),
            ]
            conn.executemany(
                """
                INSERT INTO products (
                    name, category, sku, unit_price, cost_price, stock_qty, reorder_level, supplier, expiry_date
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                products,
            )

        if conn.execute("SELECT COUNT(*) FROM sales").fetchone()[0] == 0:
            product_rows = conn.execute("SELECT id, unit_price FROM products").fetchall()
            if product_rows:
                sample_sales = [
                    (product_rows[0]["id"], 12, product_rows[0]["unit_price"], product_rows[0]["unit_price"] * 12, "2026-10-01 08:15:00", "admin"),
                    (product_rows[1]["id"], 8, product_rows[1]["unit_price"], product_rows[1]["unit_price"] * 8, "2026-10-03 11:20:00", "admin"),
                    (product_rows[3]["id"], 15, product_rows[3]["unit_price"], product_rows[3]["unit_price"] * 15, "2026-10-05 14:40:00", "admin"),
                ]
                conn.executemany(
                    "INSERT INTO sales (product_id, quantity, unit_price, total, sold_at, cashier) VALUES (?, ?, ?, ?, ?, ?)",
                    sample_sales,
                )
                for product_id, quantity, _, _, _, _ in sample_sales:
                    conn.execute(
                        "UPDATE products SET stock_qty = stock_qty - ? WHERE id = ?",
                        (quantity, product_id),
                    )


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapped_view


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        with get_db() as conn:
            user = conn.execute(
                "SELECT * FROM users WHERE username = ? AND password = ?",
                (username, password),
            ).fetchone()

        if user is not None:
            session["user_id"] = user["id"]
            session["user_name"] = user["name"]
            session["role"] = user["role"]
            flash("Welcome back! You are logged in.")
            return redirect(url_for("dashboard"))

        flash("Invalid username or password.")
        return render_template("login.html")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.")
    return redirect(url_for("login"))


@app.route("/")
@login_required
def index():
    return redirect(url_for("dashboard"))


@app.route("/dashboard")
@login_required
def dashboard():
    with get_db() as conn:
        total_products = conn.execute("SELECT COUNT(*) AS total FROM products").fetchone()["total"]
        total_stock = conn.execute("SELECT COALESCE(SUM(stock_qty),0) AS total FROM products").fetchone()["total"]
        inventory_value = conn.execute(
            "SELECT COALESCE(SUM(stock_qty * unit_price),0) AS value FROM products"
        ).fetchone()["value"]
        low_stock = conn.execute(
            "SELECT * FROM products WHERE stock_qty <= reorder_level ORDER BY stock_qty ASC LIMIT 5"
        ).fetchall()
        expiring = conn.execute(
            "SELECT * FROM products WHERE expiry_date IS NOT NULL AND expiry_date <= date('now', '+90 days') ORDER BY expiry_date ASC LIMIT 5"
        ).fetchall()
        monthly_sales = conn.execute(
            "SELECT COALESCE(SUM(total), 0) AS revenue, COALESCE(COUNT(*), 0) AS total_orders FROM sales WHERE sold_at >= date('now', 'start of month')"
        ).fetchone()
        top_products = conn.execute(
            """
            SELECT p.name, SUM(s.quantity) AS units, ROUND(SUM(s.total), 2) AS revenue
            FROM sales s
            JOIN products p ON p.id = s.product_id
            GROUP BY p.id, p.name
            ORDER BY units DESC
            LIMIT 5
            """
        ).fetchall()
        recent_sales = conn.execute(
            """
            SELECT s.id, p.name, s.quantity, s.total, s.sold_at, s.cashier
            FROM sales s
            JOIN products p ON p.id = s.product_id
            ORDER BY s.sold_at DESC
            LIMIT 5
            """
        ).fetchall()

    metrics = {
        "products": total_products,
        "stock_units": total_stock,
        "inventory_value": round(float(inventory_value), 2),
        "monthly_revenue": round(float(monthly_sales["revenue"]), 2),
        "monthly_orders": monthly_sales["total_orders"],
    }

    return render_template(
        "dashboard.html",
        user_name=session.get("user_name", "User"),
        metrics=metrics,
        low_stock=low_stock,
        expiring=expiring,
        top_products=top_products,
        recent_sales=recent_sales,
    )


@app.route("/inventory", methods=["GET"])
@login_required
def inventory():
    search = request.args.get("q", "").strip()
    query = """
        SELECT *
        FROM products
        WHERE name LIKE ? OR category LIKE ? OR sku LIKE ?
        ORDER BY name ASC
    """
    with get_db() as conn:
        products = conn.execute(
            query,
            (f"%{search}%", f"%{search}%", f"%{search}%"),
        ).fetchall()

    return render_template("inventory.html", products=products, search=search)


@app.route("/inventory/add", methods=["GET", "POST"])
@login_required
def add_inventory():
    if request.method == "POST":
        product = {
            "name": request.form.get("name", "").strip(),
            "category": request.form.get("category", "").strip(),
            "sku": request.form.get("sku", "").strip(),
            "unit_price": float(request.form.get("unit_price", 0) or 0),
            "cost_price": float(request.form.get("cost_price", 0) or 0),
            "stock_qty": int(request.form.get("stock_qty", 0) or 0),
            "reorder_level": int(request.form.get("reorder_level", 0) or 0),
            "supplier": request.form.get("supplier", "").strip(),
            "expiry_date": request.form.get("expiry_date") or None,
        }

        if not product["name"] or not product["category"] or not product["sku"]:
            flash("Product name, category and SKU are required.")
            return render_template("product_form.html", product=product)

        try:
            with get_db() as conn:
                conn.execute(
                    """
                    INSERT INTO products (
                        name, category, sku, unit_price, cost_price, stock_qty, reorder_level, supplier, expiry_date
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        product["name"],
                        product["category"],
                        product["sku"],
                        product["unit_price"],
                        product["cost_price"],
                        product["stock_qty"],
                        product["reorder_level"],
                        product["supplier"],
                        product["expiry_date"],
                    ),
                )
                product_id = conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
                if product["stock_qty"] > 0:
                    conn.execute(
                        "INSERT INTO inventory_movements (product_id, movement_type, quantity, note) VALUES (?, ?, ?, ?)",
                        (product_id, "stock_in", product["stock_qty"], "Initial inventory entry"),
                    )
        except sqlite3.IntegrityError:
            flash("SKU already exists. Please use a different code.")
            return render_template("product_form.html", product=product)

        flash("Product added successfully.")
        return redirect(url_for("inventory"))

    return render_template("product_form.html", product=None)


@app.route("/inventory/edit/<int:product_id>", methods=["GET", "POST"])
@login_required
def edit_inventory(product_id):
    with get_db() as conn:
        product = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()

    if product is None:
        flash("Product not found.")
        return redirect(url_for("inventory"))

    if request.method == "POST":
        updated = {
            "name": request.form.get("name", "").strip(),
            "category": request.form.get("category", "").strip(),
            "sku": request.form.get("sku", "").strip(),
            "unit_price": float(request.form.get("unit_price", 0) or 0),
            "cost_price": float(request.form.get("cost_price", 0) or 0),
            "stock_qty": int(request.form.get("stock_qty", 0) or 0),
            "reorder_level": int(request.form.get("reorder_level", 0) or 0),
            "supplier": request.form.get("supplier", "").strip(),
            "expiry_date": request.form.get("expiry_date") or None,
        }

        if not updated["name"] or not updated["category"] or not updated["sku"]:
            flash("Product name, category, and SKU are required.")
            return render_template("product_form.html", product=updated)

        with get_db() as conn:
            conn.execute(
                """
                UPDATE products SET
                    name = ?, category = ?, sku = ?, unit_price = ?, cost_price = ?,
                    stock_qty = ?, reorder_level = ?, supplier = ?, expiry_date = ?
                WHERE id = ?
                """,
                (
                    updated["name"],
                    updated["category"],
                    updated["sku"],
                    updated["unit_price"],
                    updated["cost_price"],
                    updated["stock_qty"],
                    updated["reorder_level"],
                    updated["supplier"],
                    updated["expiry_date"],
                    product_id,
                ),
            )
        flash("Product updated successfully.")
        return redirect(url_for("inventory"))

    return render_template("product_form.html", product=dict(product))


@app.route("/sales", methods=["GET", "POST"])
@login_required
def sales():
    with get_db() as conn:
        products = conn.execute("SELECT * FROM products ORDER BY name ASC").fetchall()
        sales_history = conn.execute(
            """
            SELECT s.id, p.name, s.quantity, s.total, s.sold_at, s.cashier
            FROM sales s
            JOIN products p ON p.id = s.product_id
            ORDER BY s.sold_at DESC
            LIMIT 20
            """
        ).fetchall()

    if request.method == "POST":
        product_id = int(request.form.get("product_id"))
        quantity = int(request.form.get("quantity", 0) or 0)
        unit_price = float(request.form.get("unit_price", 0) or 0)
        cashier = session.get("user_name", "System")

        if quantity <= 0:
            flash("Quantity must be greater than zero.")
            return render_template("sales.html", products=products, sales=sales_history)

        with get_db() as conn:
            product = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
            if product is None:
                flash("Selected product does not exist.")
                return render_template("sales.html", products=products, sales=sales_history)
            if product["stock_qty"] < quantity:
                flash("Not enough stock available for this transaction.")
                return render_template("sales.html", products=products, sales=sales_history)

            total = quantity * unit_price
            conn.execute(
                "INSERT INTO sales (product_id, quantity, unit_price, total, cashier) VALUES (?, ?, ?, ?, ?)",
                (product_id, quantity, unit_price, total, cashier),
            )
            conn.execute(
                "UPDATE products SET stock_qty = stock_qty - ? WHERE id = ?",
                (quantity, product_id),
            )
            conn.execute(
                "INSERT INTO inventory_movements (product_id, movement_type, quantity, note) VALUES (?, ?, ?, ?)",
                (product_id, "sale", quantity, f"Sale recorded by {cashier}"),
            )

        flash("Sale recorded successfully.")
        return redirect(url_for("sales"))

    return render_template("sales.html", products=products, sales=sales_history)


@app.route("/reports")
@login_required
def reports():
    with get_db() as conn:
        monthly_sales = conn.execute(
            """
            SELECT strftime('%Y-%m', sold_at) AS month, ROUND(SUM(total), 2) AS revenue
            FROM sales
            GROUP BY month
            ORDER BY month DESC
            LIMIT 6
            """
        ).fetchall()

        top_products = conn.execute(
            """
            SELECT p.name, SUM(s.quantity) AS units, ROUND(SUM(s.total), 2) AS revenue
            FROM sales s
            JOIN products p ON p.id = s.product_id
            GROUP BY p.id, p.name
            ORDER BY revenue DESC
            LIMIT 5
            """
        ).fetchall()

        low_stock = conn.execute(
            "SELECT name, stock_qty, reorder_level FROM products WHERE stock_qty <= reorder_level ORDER BY stock_qty ASC"
        ).fetchall()

    monthly_sales = [dict(item) for item in monthly_sales]
    revenue_values = [float(item["revenue"]) for item in monthly_sales]
    max_revenue = max(revenue_values) if revenue_values else 1
    for item in monthly_sales:
        item["bar_width"] = round((float(item["revenue"]) / max_revenue) * 100, 1) if max_revenue else 0

    return render_template(
        "reports.html",
        monthly_sales=monthly_sales,
        top_products=top_products,
        low_stock=low_stock,
    )


@app.before_request
def ensure_db_exists():
    if not os.path.exists(DB_PATH):
        init_db()


if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", "5001"))
    host = os.environ.get("HOST", "127.0.0.1")
    app.run(host=host, port=port, debug=False)
