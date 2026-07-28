"""
db_setup.py
Creates a small sample SQLite database so the SQL tool has something
real to query. Replace this with your actual client schema later --
the point right now is to prove the agent grounds itself in real tool
output instead of inventing rows.
"""

import sqlite3
import os
from datetime import date, timedelta
import random

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "company.db")


def build_database(path: str = DB_PATH, force: bool = False) -> str:
    if os.path.exists(path):
        if not force:
            return path
        os.remove(path)

    conn = sqlite3.connect(path)
    cur = conn.cursor()

    cur.executescript(
        """
        CREATE TABLE customers (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            city TEXT NOT NULL
        );

        CREATE TABLE products (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            price REAL NOT NULL
        );

        CREATE TABLE orders (
            id INTEGER PRIMARY KEY,
            customer_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            order_date TEXT NOT NULL,
            status TEXT NOT NULL,
            FOREIGN KEY(customer_id) REFERENCES customers(id),
            FOREIGN KEY(product_id) REFERENCES products(id)
        );
        """
    )

    cities = ["Karachi", "Lahore", "Islamabad", "Faisalabad", "Multan"]
    first_names = ["Ali", "Sara", "Bilal", "Ayesha", "Hassan", "Zainab", "Omar", "Hira"]
    last_names = ["Khan", "Ahmed", "Malik", "Raza", "Farooq", "Siddiqui"]

    customers = []
    for i in range(1, 16):
        name = f"{random.choice(first_names)} {random.choice(last_names)}"
        email = name.lower().replace(" ", ".") + f"{i}@example.com"
        city = random.choice(cities)
        customers.append((i, name, email, city))
    cur.executemany("INSERT INTO customers VALUES (?,?,?,?)", customers)

    products = [
        (1, "Wireless Mouse", "Electronics", 1499.0),
        (2, "Mechanical Keyboard", "Electronics", 6999.0),
        (3, "Office Chair", "Furniture", 15999.0),
        (4, "Standing Desk", "Furniture", 29999.0),
        (5, "USB-C Hub", "Electronics", 2499.0),
        (6, "Notebook Set", "Stationery", 399.0),
        (7, "Desk Lamp", "Furniture", 1999.0),
        (8, "Webcam 1080p", "Electronics", 3499.0),
    ]
    cur.executemany("INSERT INTO products VALUES (?,?,?,?)", products)

    statuses = ["Delivered", "Shipped", "Processing", "Cancelled"]
    orders = []
    order_id = 1
    start = date(2026, 5, 1)
    for _ in range(40):
        cust_id = random.randint(1, 15)
        prod_id = random.randint(1, 8)
        qty = random.randint(1, 4)
        d = start + timedelta(days=random.randint(0, 80))
        status = random.choice(statuses)
        orders.append((order_id, cust_id, prod_id, qty, d.isoformat(), status))
        order_id += 1
    cur.executemany("INSERT INTO orders VALUES (?,?,?,?,?,?)", orders)

    conn.commit()
    conn.close()
    return path


if __name__ == "__main__":
    p = build_database(force=True)
    print(f"Database built at {p}")
