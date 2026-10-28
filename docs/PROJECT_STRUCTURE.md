# Project structure

```text
inventory-stock-analysis-system/
├── app.py                       # Flask routes, models, validation, reporting
├── init_db.py                   # Initialize database tables
├── schema.sql                   # Explicit MySQL schema
├── requirements.txt             # Python dependencies
├── .env.example                 # Example configuration (safe to commit)
├── .gitignore                   # Excludes secrets and generated files
├── README.md                    # Setup and usage guide
├── templates/
│   ├── base.html                # Shared navigation/layout
│   ├── dashboard.html           # Dashboard cards and recent transactions
│   ├── products.html            # Product management
│   ├── suppliers.html           # Supplier management
│   ├── transactions.html        # Stock-in/out forms and history
│   └── reports.html             # Valuation, low-stock and movement reports
├── static/
│   └── css/style.css            # Application styles
├── tests/
│   └── test_stock_logic.py      # Basic stock-rule unit tests
└── docs/
    └── PROJECT_STRUCTURE.md
```

## Main calculation
Current stock = opening stock + stock-in + adjustment-in - stock-out - adjustment-out.

## Transaction types
- `IN`: goods received
- `OUT`: goods issued/sold
- `ADJUSTMENT_IN`: positive correction
- `ADJUSTMENT_OUT`: negative correction

Every adjustment is a transaction row with a timestamp and optional notes; transaction history is retained.
