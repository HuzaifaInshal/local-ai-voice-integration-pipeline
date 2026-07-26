import os
import sqlite3
from datetime import datetime, timedelta

def create_and_seed_db(db_path: str = "./data/banking.db"):
    """Creates a sample SQLite database representing internal banking system schema."""
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 1. Accounts Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS accounts (
        account_id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_name TEXT NOT NULL,
        account_type TEXT NOT NULL,
        balance REAL NOT NULL,
        currency TEXT DEFAULT 'USD',
        status TEXT DEFAULT 'Active',
        created_at TEXT NOT NULL
    );
    """)

    # 2. Transactions Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS transactions (
        transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
        account_id INTEGER NOT NULL,
        transaction_type TEXT NOT NULL,
        amount REAL NOT NULL,
        category TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        FOREIGN KEY (account_id) REFERENCES accounts (account_id)
    );
    """)

    # 3. Loans Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS loans (
        loan_id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_name TEXT NOT NULL,
        loan_type TEXT NOT NULL,
        principal_amount REAL NOT NULL,
        interest_rate REAL NOT NULL,
        outstanding_balance REAL NOT NULL,
        status TEXT DEFAULT 'Active'
    );
    """)

    # Clear existing records for clean seeding
    cursor.execute("DELETE FROM transactions;")
    cursor.execute("DELETE FROM accounts;")
    cursor.execute("DELETE FROM loans;")

    # Seed Accounts
    accounts_data = [
        ("Acme Corp Vault", "Commercial Savings", 4500000.00, "USD", "Active", "2023-01-15"),
        ("Global Logistics LLC", "Checking", 1250000.50, "USD", "Active", "2023-03-22"),
        ("Horizon Ventures", "Investment", 8900000.00, "USD", "Active", "2022-11-05"),
        ("Starlight Tech", "Checking", 340000.75, "USD", "Active", "2024-02-10"),
        ("Apex Capital", "Commercial Savings", 12400000.00, "USD", "Active", "2021-08-30"),
    ]
    cursor.executemany("""
    INSERT INTO accounts (customer_name, account_type, balance, currency, status, created_at)
    VALUES (?, ?, ?, ?, ?, ?);
    """, accounts_data)

    # Seed Transactions
    now = datetime.now()
    transactions_data = [
        (1, "Credit", 250000.00, "Wire Transfer", (now - timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S")),
        (1, "Debit", 45000.00, "Payroll", (now - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")),
        (2, "Credit", 120000.00, "Vendor Payment", (now - timedelta(days=3)).strftime("%Y-%m-%d %H:%M:%S")),
        (2, "Debit", 15000.00, "Utilities", (now - timedelta(hours=5)).strftime("%Y-%m-%d %H:%M:%S")),
        (3, "Credit", 500000.00, "Dividend Income", (now - timedelta(days=5)).strftime("%Y-%m-%d %H:%M:%S")),
        (4, "Debit", 8200.00, "Software Subscription", (now - timedelta(days=4)).strftime("%Y-%m-%d %H:%M:%S")),
        (5, "Credit", 1000000.00, "Treasury yield", (now - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")),
    ]
    cursor.executemany("""
    INSERT INTO transactions (account_id, transaction_type, amount, category, timestamp)
    VALUES (?, ?, ?, ?, ?);
    """, transactions_data)

    # Seed Loans
    loans_data = [
        ("Acme Corp Vault", "Equipment Loan", 500000.00, 4.5, 320000.00, "Active"),
        ("Global Logistics LLC", "Commercial Mortgage", 2000000.00, 5.2, 1750000.00, "Active"),
        ("Starlight Tech", "Revolving Credit Line", 150000.00, 6.0, 45000.00, "Active"),
    ]
    cursor.executemany("""
    INSERT INTO loans (customer_name, loan_type, principal_amount, interest_rate, outstanding_balance, status)
    VALUES (?, ?, ?, ?, ?, ?);
    """, loans_data)

    conn.commit()
    conn.close()
    print(f"Mock Banking Database successfully seeded at: {db_path}")

if __name__ == "__main__":
    create_and_seed_db()
