import os
from datetime import datetime
from decimal import Decimal, InvalidOperation
from io import BytesIO

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from dotenv import load_dotenv
from flask import Flask, flash, redirect, render_template, request, send_file, url_for
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func, case
from sqlalchemy.exc import IntegrityError

load_dotenv()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-only-change-me")
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
    "DATABASE_URL",
    "mysql+pymysql://root:password@localhost:3306/inventory_db"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)


class Supplier(db.Model):
    __tablename__ = "suppliers"
    supplier_id = db.Column(db.Integer, primary_key=True)
    supplier_name = db.Column(db.String(150), unique=True, nullable=False)
    contact_email = db.Column(db.String(255))
    phone = db.Column(db.String(40))
    created_at = db.Column(db.DateTime, server_default=func.now())


class Product(db.Model):
    __tablename__ = "products"
    product_id = db.Column(db.Integer, primary_key=True)
    sku = db.Column(db.String(80), unique=True, nullable=False)
    product_name = db.Column(db.String(180), nullable=False)
    category = db.Column(db.String(100), nullable=False, default="General")
    opening_stock = db.Column(db.Integer, nullable=False, default=0)
    reorder_level = db.Column(db.Integer, nullable=False, default=0)
    unit_cost = db.Column(db.Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    created_at = db.Column(db.DateTime, server_default=func.now())
    transactions = db.relationship("StockTransaction", back_populates="product", lazy=True)

    @property
    def current_stock(self):
        incoming = sum(t.quantity for t in self.transactions
                       if t.transaction_type in ("IN", "ADJUSTMENT_IN"))
        outgoing = sum(t.quantity for t in self.transactions
                       if t.transaction_type in ("OUT", "ADJUSTMENT_OUT"))
        return self.opening_stock + incoming - outgoing

    @property
    def stock_value(self):
        return float(self.current_stock * float(self.unit_cost))


class StockTransaction(db.Model):
    __tablename__ = "stock_transactions"
    transaction_id = db.Column(db.BigInteger, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.product_id"), nullable=False)
    transaction_date = db.Column(db.DateTime, nullable=False, default=datetime.now)
    transaction_type = db.Column(
        db.Enum("IN", "OUT", "ADJUSTMENT_IN", "ADJUSTMENT_OUT", name="transaction_type"),
        nullable=False
    )
    quantity = db.Column(db.Integer, nullable=False)
    supplier_id = db.Column(db.Integer, db.ForeignKey("suppliers.supplier_id"), nullable=True)
    notes = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, server_default=func.now())
    product = db.relationship("Product", back_populates="transactions")
    supplier = db.relationship("Supplier")


def get_stock(product_id):
    """Calculate stock from opening balance and all posted transaction rows."""
    product = db.session.get(Product, product_id)
    if not product:
        return None
    totals = db.session.query(
        func.coalesce(func.sum(case(
            (StockTransaction.transaction_type.in_(["IN", "ADJUSTMENT_IN"]),
             StockTransaction.quantity), else_=0)), 0).label("incoming"),
        func.coalesce(func.sum(case(
            (StockTransaction.transaction_type.in_(["OUT", "ADJUSTMENT_OUT"]),
             StockTransaction.quantity), else_=0)), 0).label("outgoing")
    ).filter(StockTransaction.product_id == product_id).one()
    return product.opening_stock + int(totals.incoming) - int(totals.outgoing)


def parse_nonnegative_int(value, label):
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{label} must be a whole number.")
    if number < 0:
        raise ValueError(f"{label} cannot be negative.")
    return number


def parse_money(value, label):
    try:
        number = Decimal(value)
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(f"{label} must be a valid amount.")
    if not number.is_finite() or number < 0:
        raise ValueError(f"{label} cannot be negative.")
    return number.quantize(Decimal("0.01"))


@app.route("/")
def dashboard():
    products = Product.query.order_by(Product.product_name).all()
    stock_values = [p.current_stock for p in products]
    low_stock = [p for p in products if p.current_stock <= p.reorder_level]
    total_units = int(np.sum(stock_values)) if stock_values else 0
    inventory_value = sum(p.current_stock * float(p.unit_cost) for p in products)
    recent = StockTransaction.query.order_by(
        StockTransaction.transaction_date.desc(),
        StockTransaction.transaction_id.desc()
    ).limit(8).all()
    return render_template(
        "dashboard.html", products=products, low_stock=low_stock,
        total_products=len(products), total_units=total_units,
        inventory_value=inventory_value, recent=recent
    )


@app.route("/products", methods=["GET", "POST"])
def products():
    if request.method == "POST":
        try:
            sku = request.form.get("sku", "").strip()
            name = request.form.get("product_name", "").strip()
            category = request.form.get("category", "General").strip() or "General"
            if not sku or not name:
                raise ValueError("SKU and product name are required.")
            opening = parse_nonnegative_int(request.form.get("opening_stock"), "Opening stock")
            reorder = parse_nonnegative_int(request.form.get("reorder_level"), "Reorder level")
            cost = parse_money(request.form.get("unit_cost"), "Unit cost")
            db.session.add(Product(sku=sku, product_name=name, category=category,
                                   opening_stock=opening, reorder_level=reorder, unit_cost=cost))
            db.session.commit()
            flash("Product added successfully.", "success")
            return redirect(url_for("products"))
        except ValueError as exc:
            db.session.rollback()
            flash(str(exc), "danger")
        except IntegrityError:
            db.session.rollback()
            flash("That SKU already exists. Use a unique SKU.", "danger")
    items = Product.query.order_by(Product.product_name).all()
    return render_template("products.html", products=items)


@app.route("/suppliers", methods=["GET", "POST"])
def suppliers():
    if request.method == "POST":
        name = request.form.get("supplier_name", "").strip()
        email = request.form.get("contact_email", "").strip() or None
        phone = request.form.get("phone", "").strip() or None
        if not name:
            flash("Supplier name is required.", "danger")
        else:
            try:
                db.session.add(Supplier(supplier_name=name, contact_email=email, phone=phone))
                db.session.commit()
                flash("Supplier added successfully.", "success")
                return redirect(url_for("suppliers"))
            except IntegrityError:
                db.session.rollback()
                flash("That supplier name already exists.", "danger")
    items = Supplier.query.order_by(Supplier.supplier_name).all()
    return render_template("suppliers.html", suppliers=items)


@app.route("/transactions", methods=["GET", "POST"])
def transactions():
    if request.method == "POST":
        try:
            product_id = int(request.form.get("product_id", ""))
            txn_type = request.form.get("transaction_type", "")
            if txn_type not in ("IN", "OUT", "ADJUSTMENT_IN", "ADJUSTMENT_OUT"):
                raise ValueError("Choose a valid transaction type.")
            quantity = parse_nonnegative_int(request.form.get("quantity"), "Quantity")
            if quantity <= 0:
                raise ValueError("Quantity must be greater than zero.")
            product = db.session.get(Product, product_id)
            if product is None:
                raise ValueError("Select a valid product.")
            supplier_raw = request.form.get("supplier_id", "").strip()
            supplier_id = int(supplier_raw) if supplier_raw else None
            if supplier_id and db.session.get(Supplier, supplier_id) is None:
                raise ValueError("Select a valid supplier.")
            if txn_type in ("OUT", "ADJUSTMENT_OUT"):
                # Lock the product row while validating to reduce concurrent stock-out races.
                db.session.query(Product).filter_by(product_id=product_id).with_for_update().one()
                current = get_stock(product_id)
                if quantity > current:
                    raise ValueError(
                        f"Insufficient stock. Current stock is {current}; requested stock-out is {quantity}."
                    )
            date_raw = request.form.get("transaction_date", "").strip()
            txn_date = datetime.strptime(date_raw, "%Y-%m-%dT%H:%M") if date_raw else datetime.now()
            notes = request.form.get("notes", "").strip() or None
            db.session.add(StockTransaction(
                product_id=product_id, transaction_type=txn_type, quantity=quantity,
                supplier_id=supplier_id, transaction_date=txn_date, notes=notes
            ))
            db.session.commit()
            flash("Stock transaction recorded.", "success")
            return redirect(url_for("transactions"))
        except ValueError as exc:
            db.session.rollback()
            flash(str(exc), "danger")
        except (IntegrityError, OverflowError) as exc:
            db.session.rollback()
            flash("Transaction could not be saved. Check the selected product and supplier.", "danger")
    products_list = Product.query.order_by(Product.product_name).all()
    suppliers_list = Supplier.query.order_by(Supplier.supplier_name).all()
    history = StockTransaction.query.order_by(
        StockTransaction.transaction_date.desc(),
        StockTransaction.transaction_id.desc()
    ).limit(100).all()
    return render_template("transactions.html", products=products_list,
                           suppliers=suppliers_list, transactions=history)


@app.route("/reports")
def reports():
    products_list = Product.query.order_by(Product.product_name).all()
    rows = []
    for p in products_list:
        txns = p.transactions
        rows.append({
            "SKU": p.sku,
            "Product": p.product_name,
            "Category": p.category,
            "Opening Stock": p.opening_stock,
            "Stock In": sum(t.quantity for t in txns if t.transaction_type in ("IN", "ADJUSTMENT_IN")),
            "Stock Out": sum(t.quantity for t in txns if t.transaction_type in ("OUT", "ADJUSTMENT_OUT")),
            "Current Stock": p.current_stock,
            "Reorder Level": p.reorder_level,
            "Unit Cost": float(p.unit_cost),
            "Stock Value": p.current_stock * float(p.unit_cost),
        })
    frame = pd.DataFrame(rows)
    if not frame.empty:
        frame["Status"] = np.where(frame["Current Stock"] <= frame["Reorder Level"],
                                   "REORDER", "OK")
        low_stock = frame[frame["Status"] == "REORDER"].to_dict("records")
        total_value = float(np.sum(frame["Stock Value"].to_numpy(dtype=float)))
    else:
        low_stock, total_value = [], 0.0
    return render_template("reports.html", rows=rows, low_stock=low_stock,
                           total_value=total_value)


@app.route("/reports/movement.csv")
def movement_csv():
    products_list = Product.query.order_by(Product.product_name).all()
    rows = []
    for p in products_list:
        txns = p.transactions
        rows.append({
            "SKU": p.sku, "Product": p.product_name,
            "Stock In": sum(t.quantity for t in txns if t.transaction_type in ("IN", "ADJUSTMENT_IN")),
            "Stock Out": sum(t.quantity for t in txns if t.transaction_type in ("OUT", "ADJUSTMENT_OUT")),
            "Current Stock": p.current_stock,
            "Reorder Level": p.reorder_level,
            "Unit Cost": float(p.unit_cost),
            "Stock Value": p.current_stock * float(p.unit_cost),
        })
    output = BytesIO()
    pd.DataFrame(rows).to_csv(output, index=False)
    output.seek(0)
    return send_file(output, mimetype="text/csv", as_attachment=True,
                     download_name="inventory_report.csv")


@app.route("/reports/stock-chart.png")
def stock_chart():
    items = Product.query.order_by(Product.product_name).all()
    names = [p.product_name for p in items]
    stocks = [p.current_stock for p in items]
    reorder = [p.reorder_level for p in items]
    fig, ax = plt.subplots(figsize=(10, 5))
    positions = np.arange(len(names))
    if names:
        ax.bar(positions - 0.2, stocks, width=0.4, label="Current stock")
        ax.bar(positions + 0.2, reorder, width=0.4, label="Reorder level")
        ax.set_xticks(positions)
        ax.set_xticklabels(names, rotation=35, ha="right")
        ax.legend()
    else:
        ax.text(0.5, 0.5, "Add products to view stock levels",
                ha="center", va="center", transform=ax.transAxes)
    ax.set_title("Current Stock vs Reorder Level")
    ax.set_ylabel("Units")
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    image_buffer = BytesIO()
    fig.savefig(image_buffer, format="png", dpi=140)
    plt.close(fig)
    image_buffer.seek(0)
    return send_file(image_buffer, mimetype="image/png")


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=os.getenv("FLASK_DEBUG", "0") == "1")
