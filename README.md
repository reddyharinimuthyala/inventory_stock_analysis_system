# Inventory and Stock Analysis System

A Flask + MySQL inventory application for managing products, suppliers, stock-in/stock-out transactions, low-stock alerts, inventory valuation, and movement charts.

## Features
- Product and supplier management
- Stock-in and stock-out transaction recording
- Current stock calculated from opening stock plus transactions
- Prevents stock-out transactions that would make stock negative
- Transaction history for auditability
- Low-stock report based on configurable reorder levels
- Inventory valuation and movement summaries using Pandas and NumPy
- Matplotlib stock-level chart

## Tech stack
- Python 3.10+
- Flask
- MySQL
- SQLAlchemy
- Pandas, NumPy, Matplotlib

## 1. Create a virtual environment

### Windows PowerShell
```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, use:
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

## 2. Install dependencies
```powershell
pip install -r requirements.txt
```

## 3. Create the MySQL database
Open MySQL Workbench or the MySQL command line and run:
```sql
CREATE DATABASE inventory_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

## 4. Configure the database
Copy `.env.example` to `.env` and set your MySQL username/password:
```powershell
Copy-Item .env.example .env
```
Edit `DATABASE_URL` in `.env`. Example:
```env
DATABASE_URL=mysql+pymysql://root:your_password@localhost:3306/inventory_db
SECRET_KEY=replace-this-with-a-long-random-secret
```
If your password contains special URL characters, URL-encode it.

## 5. Initialize tables and run
```powershell
python init_db.py
python app.py
```
Open http://127.0.0.1:5000

## How stock is calculated
`current_stock = opening_stock + total_stock_in - total_stock_out`

Stock is derived from the opening balance and immutable transaction records. The app validates stock-out transactions inside a database transaction and rejects a transaction if it would make stock negative. Do not manually edit transaction rows in production.

## Notes
- This is an educational starter project, not a production-hardened inventory platform.
- Add authentication/roles, CSRF protection, migrations, backups, and automated tests before real business use.
- `supplier_id` is optional on a stock transaction.
