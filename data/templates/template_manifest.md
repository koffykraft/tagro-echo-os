# Canonical CSV Templates

These files are header-only import/export templates governed by `src/import_export/csv_contracts.py`.

Datasets: users, branches, products, prices, customers, suppliers, quotes, quote_lines, sales, sale_lines, purchases, purchase_lines, stock, stock_movements, machines, service_jobs, service_events, cash_closings, bank_transactions, payments, payment_allocations.

BUSY and other accounting systems are adapters to these contracts; they are not the operational source of truth.
