import sqlite3

def init_db():
    conn = sqlite3.connect('farmup.db')
    cursor = conn.cursor()
    
    # Existing users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            mobile TEXT NOT NULL UNIQUE,
            state TEXT NOT NULL,
            district TEXT NOT NULL,
            village_town TEXT NOT NULL
        )
    ''')
    
    # table to cache & store mandi prices from API
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS mandi_prices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            state TEXT NOT NULL,
            district TEXT NOT NULL,
            market TEXT NOT NULL,
            commodity TEXT NOT NULL,
            variety TEXT,
            arrival_date TEXT,
            min_price TEXT,
            max_price TEXT,
            modal_price TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(state, district, market, commodity, variety)
        )
    ''')
    
    conn.commit()
    conn.close()
    print("Database 'farmup.db' initialized with users and mandi_prices tables!")

if __name__ == '__main__':
    init_db()