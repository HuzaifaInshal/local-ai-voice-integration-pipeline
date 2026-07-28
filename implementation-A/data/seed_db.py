import os
import sqlite3
from datetime import datetime, timedelta

def create_and_seed_db(db_path: str = "./data/banking.db"):
    """Creates and seeds the SQLite banking database with accounts, transactions, loans, clients, and ratings."""
    db_dir = os.path.dirname(db_path)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)

    print(f"🌱 Seeding SQLite database at: {db_path}")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.executescript("""
    DROP TABLE IF EXISTS ratings;
    DROP TABLE IF EXISTS clients;
    DROP TABLE IF EXISTS accounts;
    DROP TABLE IF EXISTS loans;
    DROP TABLE IF EXISTS transactions;

    CREATE TABLE accounts (
        account_id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_name TEXT NOT NULL,
        account_type TEXT NOT NULL,
        balance REAL NOT NULL,
        currency TEXT DEFAULT 'USD',
        status TEXT DEFAULT 'Active',
        created_at TEXT NOT NULL
    );

    CREATE TABLE transactions (
        transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
        account_id INTEGER NOT NULL,
        transaction_type TEXT NOT NULL,
        amount REAL NOT NULL,
        category TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        FOREIGN KEY (account_id) REFERENCES accounts (account_id)
    );

    CREATE TABLE loans (
        loan_id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_name TEXT NOT NULL,
        loan_type TEXT NOT NULL,
        principal_amount REAL NOT NULL,
        interest_rate REAL NOT NULL,
        outstanding_balance REAL NOT NULL,
        status TEXT DEFAULT 'Active'
    );

    CREATE TABLE clients (
        crimsid INTEGER PRIMARY KEY,
        t24_id TEXT NOT NULL UNIQUE,
        customer_name TEXT NOT NULL,
        pr_category TEXT NOT NULL,
        business_segment TEXT NOT NULL,
        branch_code INTEGER NOT NULL,
        branch_name TEXT NOT NULL,
        sbp_parent TEXT NOT NULL,
        sbp_child TEXT NOT NULL,
        client_sales REAL NOT NULL,
        client_equity REAL NOT NULL,
        client_opening_date TEXT NOT NULL,
        legal_entity TEXT NOT NULL,
        pep TEXT NOT NULL
    );

    CREATE TABLE ratings (
        rating_id INTEGER PRIMARY KEY AUTOINCREMENT,
        t24_id TEXT NOT NULL,
        financial_year TEXT NOT NULL,
        pr_category TEXT NOT NULL,
        base_rating INTEGER NOT NULL,
        final_rating INTEGER NOT NULL,
        orr_authorized_by_bu_date TEXT NOT NULL,
        orr_authorized_by_cd_date TEXT NOT NULL,
        FOREIGN KEY (t24_id) REFERENCES clients (t24_id)
    );
    """)

    # 1. Seed Accounts
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

    # 2. Seed Transactions
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

    # 3. Seed Loans
    loans_data = [
        ("Acme Corp Vault", "Equipment Loan", 500000.00, 4.5, 320000.00, "Active"),
        ("Global Logistics LLC", "Commercial Mortgage", 2000000.00, 5.2, 1750000.00, "Active"),
        ("Starlight Tech", "Revolving Credit Line", 150000.00, 6.0, 45000.00, "Active"),
    ]
    cursor.executemany("""
    INSERT INTO loans (customer_name, loan_type, principal_amount, interest_rate, outstanding_balance, status)
    VALUES (?, ?, ?, ?, ?, ?);
    """, loans_data)

    # 4. Seed Clients
    clients_data = [
        (12355, '145345670000', 'Fauji Fertilizer', 'Corporate', 'CIBG', 5, 'Main Branch', 'MANUFACTURE OF CHEMICALS AND CHEMICAL PRODUCTS', 'Manufacture Of Fertilizers And Nitrogen Compounds', 5000000000.0, 25000000.0, '5/25/2024', 'Public Limited Company - Unlisted', 'No'),
        (12356, '145345680000', 'Fatima Energy', 'Corporate', 'CIBG', 5, 'Main Branch', 'ELECTRICITY GAS STEAM AND AIR CONDITIONING SUPPLY', 'Electr Power Generation Transmission And Distributn- Hydal', 2348900000.0, 123450000.0, '12/3/2021', 'Public Limited Company - Unlisted', 'No'),
        (12357, '145345690000', 'Master Textile Mills', 'Corporate', 'CIBG', 280, 'ISB Main', 'MANUFACTURE OF TEXTILES', 'Preparation And Spinning Of Textile Fibres - Others', 2678900000.0, 323455555.0, '5/27/2024', 'Private Limited Company - Unlisted', 'Yes'),
        (12358, '145345700000', 'Afia Noor Textile Mills', 'Commercial', 'RBG', 12, 'Urdu Bazar', 'MANUFACTURE OF TEXTILES', 'Preparation And Spinning Of Textile Fibres - Others', 1432322222.0, 254432333.0, '5/28/2024', 'Private Limited Company - Unlisted', 'Yes'),
        (12359, '145345710000', 'Euro Oil Traders', 'Corporate', 'CIBG', 56, 'Faisalabad Main', 'RETAIL TRADE EXCEPT OF MOTOR VEHICLES AND MOTORCYCLES', 'Others Retail Sale N.E.C', 2897892000.0, 25475544.0, '5/29/2024', 'Private Limited Company - Unlisted', 'Yes'),
        (12360, '145345720000', 'Prime Oil & Ghee Mills', 'Commercial', 'RBG', 24, 'Jodia Bazar', 'MANUFACTURE OF FOOD PRODUCTS', 'Manufacture Of Vegetable And Animal Oils And Fats', 2897892001.0, 15475544.0, '4/30/2022', 'Private Limited Company - Unlisted', 'Yes'),
        (12361, '145345730000', 'Hajveri Oil Extraction', 'Commercial', 'RBG', 89, 'Jodia Bazar', 'MANUFACTURE OF FOOD PRODUCTS', 'Manufacture Of Other Food Products N.E.C.,', 287892002.0, 25423544.0, '5/31/2024', 'Private Limited Company - Unlisted', 'No'),
        (12362, '145345740000', 'Muhammad Imran Anwar', 'SE', 'IBG', 3344, 'IBG - Multan', 'INDIVIDUALS', 'OTHER SALARIED PERSONS', 2892003.0, 23375544.0, '6/10/2019', 'Individual', 'No'),
        (12363, '145345750000', 'Ali Raza Anwar', 'SE', 'RBG', 212, 'Main Sialkot', 'INDIVIDUALS', 'OTHER SALARIED PERSONS', 1357200.0, 10325378.0, '6/2/2024', 'Individual', 'No'),
        (12364, '145345760000', 'Pak Green Pharmacy', 'ME', 'IBG', 4467, 'IBG - Sialkot', 'HUMAN HEALTH ACTIVITIES', 'Other Human Health Activities', 27892005.0, 25473222.0, '6/3/2024', 'Individual', 'Yes'),
        (12365, '145345770000', 'Noor Pharma Link', 'ME', 'RBG', 39, 'Susan Road - Multan', 'HUMAN HEALTH ACTIVITIES', 'Other Human Health Activities', 18978926.0, 54475544.0, '6/4/2024', 'Private Limited Company - Unlisted', 'Yes'),
        (12366, '145345780000', 'OIL & GAS DEVELOPMENT COMPANY LTD', 'Corporate', 'CIBG', 39, 'Gulberg Main', 'MANUFACTURE OF CHEMICALS AND CHEMICAL PRODUCTS', 'Manufacture Of Fertilizers And Nitrogen Compounds', 2832892007.0, 35475544.0, '11/5/2024', 'Public Limited Company - listed', 'No'),
        (12367, '145345790000', 'SUI SOUTHERN GAS COMPANY', 'Corporate', 'CIBG', 5, 'Gulberg Main', 'PUBLIC SECTOR ENTERPRISES', 'Sui Southern Gas Company Ltd.', 5897892008.0, 11575544.0, '6/9/2022', 'Public Limited Company - listed', 'No'),
        (12368, '145345800000', 'Minhas Autos', 'SE', 'IBG', 2344, 'IBG - Gulberg', 'WHOLESALE TRADE EXCEPT OF MOTOR VEHICLES AND MOTORCYCLES', 'Non-Specialized Wholesale Trade', 1157200.0, 27875544.0, '12/7/2024', 'Sole Proprietorship', 'No'),
        (12369, '145345810000', 'Nexgen Auto (Private) Limited', 'ME', 'RBG', 654, 'F-10 Markaz, Islamabad', 'MANUFACTURE OF MOTOR VEHICLES TRAILERS AND SEMI-TRAILERS', 'Manufacture Of Motor Vehicles', 21292005.0, 25475544.0, '6/8/2024', 'Sole Proprietorship', 'No'),
        (12370, '145345820000', 'Faisalabad Cloth House', 'Commercial', 'RBG', 5, 'Hyderabad Main', 'MANUFACTURE OF TEXTILES', 'Preparation And Spinning Of Textile Fibres - Cotton', 2897892011.0, 11575544.0, '6/9/2024', 'Private Limited Company - Unlisted', 'No'),
        (12371, '145345830000', 'Fazal Cloth House', 'ME', 'IBG', 2232, 'IBG - Quetta', 'MANUFACTURE OF TEXTILES', 'Preparation And Spinning Of Textile Fibres - Cotton', 12292005.0, 21275544.0, '6/10/2024', 'Private Limited Company - Unlisted', 'No'),
        (12372, '145345840000', 'Qasim Autos', 'SE', 'IBG', 6544, 'IBG - Bhawalpur', 'MANUFACTURE OF MOTOR VEHICLES TRAILERS AND SEMI-TRAILERS', 'Manufacture Of Motor Vehicles', 9792013.0, 25475544.0, '6/11/2024', 'Sole Proprietorship', 'No'),
        (12373, '145345850000', 'Roshan Agri Business', 'Agri', 'RBG', 691, 'Vihari', 'Crop Animal Production', 'Post Harvest Crop Activities', 7892014.0, 25475544.0, '6/12/2024', 'Sole Proprietorship', 'No'),
        (12374, '145345860000', 'Cheema Agri Farm', 'Agri', 'RBG', 231, 'Nawabshah', 'Crop Animal Production', 'Post Harvest Crop Activities', 2897205.0, 25475544.0, '6/13/2024', 'Sole Proprietorship', 'No')
    ]
    cursor.executemany("""
    INSERT INTO clients (
        crimsid, t24_id, customer_name, pr_category, business_segment,
        branch_code, branch_name, sbp_parent, sbp_child, client_sales,
        client_equity, client_opening_date, legal_entity, pep
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, clients_data)

    # 5. Seed Ratings
    ratings_data = [
        ('145345670000', '6/30/2024', 'Corporate', 5, 5, '8/31/2024', '8/31/2024'),
        ('145345670000', '6/30/2025', 'Commercial', 4, 4, '8/17/2025', '8/23/2025'),
        ('145345670000', '6/30/2026', 'Corporate', 3, 3, '7/2/2026', '7/15/2026'),
        ('145345780000', '6/30/2025', 'Corporate', 2, 2, '7/3/2025', '7/3/2025'),
        ('145345780000', '6/30/2026', 'Corporate', 1, 1, '7/19/2026', '7/20/2026'),
        ('145345750000', '6/30/2025', 'SE', 7, 7, '10/5/2025', '10/23/2025'),
        ('145345750000', '6/30/2025', 'SE', 8, 12, '7/3/2026', '7/10/2026'),
        ('145345760000', '6/30/2024', 'ME', 5, 5, '8/31/2024', '8/31/2024'),
        ('145345760000', '6/30/2025', 'ME', 6, 6, '8/17/2025', '8/23/2025'),
        ('145345760000', '6/30/2026', 'ME', 4, 4, '7/2/2026', '7/15/2026'),
        ('145345860000', '6/30/2026', 'Agri', 6, 7, '7/12/2026', '7/20/2026')
    ]
    cursor.executemany("""
    INSERT INTO ratings (
        t24_id, financial_year, pr_category, base_rating,
        final_rating, orr_authorized_by_bu_date, orr_authorized_by_cd_date
    ) VALUES (?, ?, ?, ?, ?, ?, ?);
    """, ratings_data)

    conn.commit()
    conn.close()
    print(f"✅ Mock Banking Database successfully seeded at: {db_path}")

if __name__ == "__main__":
    create_and_seed_db()
