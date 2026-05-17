import sqlite3
import time
import random
import datetime

DB_FILE = 'sales.db'

def setup_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    # Create table for orders
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id TEXT,
            customer_id TEXT,
            category TEXT,
            region TEXT,
            amount REAL,
            order_date DATETIME
        )
    ''')
    
    # Check if empty, populate initial historical data
    cursor.execute("SELECT COUNT(*) FROM orders")
    if cursor.fetchone()[0] == 0:
        print("Populating initial data...")
        categories = ['Electronics', 'Accessories', 'Furniture']
        regions = ['Hanoi', 'HCM', 'Danang']
        
        # Insert last 6 months of data
        now = datetime.datetime.now()
        for i in range(500):
            days_ago = random.randint(1, 180)
            date = now - datetime.timedelta(days=days_ago)
            cursor.execute('''
                INSERT INTO orders (order_id, customer_id, category, region, amount, order_date)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                f"ORD-{random.randint(1000, 9999)}",
                f"CUST-{random.randint(100, 200)}",
                random.choice(categories),
                random.choice(regions),
                random.uniform(500000, 5000000),
                date.strftime('%Y-%m-%d %H:%M:%S')
            ))
        conn.commit()
    conn.close()

def simulate_real_time():
    setup_db()
    print("Database ready. Simulating real-time orders (1 order per 10s)...")
    categories = ['Electronics', 'Accessories', 'Furniture']
    regions = ['Hanoi', 'HCM', 'Danang']
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    while True:
        try:
            # Sometime simulate a drop in Danang or Hanoi to trigger anomaly
            is_anomaly = random.random() < 0.1 # 10% chance to simulate bad hour
            
            amount = random.uniform(500000, 5000000)
            if is_anomaly:
                amount = random.uniform(50000, 200000) # Extremely low amount
                
            cursor.execute('''
                INSERT INTO orders (order_id, customer_id, category, region, amount, order_date)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                f"RT-{random.randint(1000, 9999)}",
                f"CUST-{random.randint(100, 200)}",
                random.choice(categories),
                random.choice(regions),
                amount,
                datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ))
            conn.commit()
            print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] Inserted new order. Amount: {amount:.2f}")
            time.sleep(10) # 10 seconds per order for simulation
        except KeyboardInterrupt:
            break
    conn.close()

if __name__ == "__main__":
    simulate_real_time()
