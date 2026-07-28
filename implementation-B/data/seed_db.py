import os
import sqlite3

def seed_database(db_path: str = "./data/banking.db"):
    db_dir = os.path.dirname(db_path)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)

    print(f"🌱 Seeding mock SQLite banking database at: {db_path}")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.executescript("""
    DROP TABLE IF EXISTS accounts;
    DROP TABLE IF EXISTS loans;
    DROP TABLE IF EXISTS transactions;

    CREATE TABLE accounts (
        account_id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_name TEXT NOT NULL,
        account_type TEXT NOT NULL,
        balance REAL NOT NULL,
        currency TEXT NOT NULL DEFAULT 'USD',
        status TEXT NOT NULL DEFAULT 'Active'
    );

    CREATE TABLE loans (
        loan_id INTEGER PRIMARY KEY AUTOINCREMENT,
        borrower_name TEXT NOT NULL,
        loan_type TEXT NOT NULL,
        principal_amount REAL NOT NULL,
        outstanding_balance REAL NOT NULL,
        interest_rate REAL NOT NULL,
        status TEXT NOT NULL DEFAULT 'Active'
    );

    CREATE TABLE transactions (
        transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
        account_id INTEGER NOT NULL,
        type TEXT NOT NULL,
        amount REAL NOT NULL,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        description TEXT
    );

    INSERT INTO accounts (customer_name, account_type, balance, currency, status) VALUES
    ('Apex Capital', 'Commercial Savings', 12400000.00, 'USD', 'Active'),
    ('Horizon Ventures', 'Investment', 8900000.00, 'USD', 'Active'),
    ('Acme Corp Vault', 'Checking', 4500000.00, 'USD', 'Active'),
    ('Global Logistics LLC', 'Checking', 1250000.50, 'USD', 'Active'),
    ('Starlight Tech', 'Savings', 340000.75, 'USD', 'Active'),
    ('Nexus Energy', 'Commercial Checking', 9800000.00, 'USD', 'Active');

    INSERT INTO loans (borrower_name, loan_type, principal_amount, outstanding_balance, interest_rate, status) VALUES
    ('Apex Capital', 'Syndicated Commercial', 15000000.00, 11200000.00, 5.25, 'Active'),
    ('Global Logistics LLC', 'Fleet Equipment Loan', 3500000.00, 2100000.00, 6.10, 'Active'),
    ('Acme Corp Vault', 'Real Estate Mortgage', 8000000.00, 6400000.00, 4.85, 'Active'),
    ('Starlight Tech', 'R&D Innovation Credit', 1000000.00, 450000.00, 5.75, 'Active');

    INSERT INTO transactions (account_id, type, amount, description) VALUES
    (1, 'Credit', 2500000.00, 'Quarterly Dividend Wire Transfer'),
    (2, 'Debit', 450000.00, 'Venture Capital Disbursal'),
    (3, 'Credit', 120000.00, 'Client Invoice Settlement'),
    (4, 'Debit', 75000.00, 'Logistics Fuel Supply Payment'),
    (1, 'Credit', 500000.00, 'Corporate Bond Interest Yield');
    """)

    conn.commit()
    conn.close()
    print("✅ Database successfully seeded!")

if __name__ == "__main__":
    seed_database()
