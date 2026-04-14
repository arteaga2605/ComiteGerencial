# data/database.py
import sqlite3
from config import DB_PATH
import pandas as pd
from datetime import datetime

class Database:
    def __init__(self):
        self.conn = sqlite3.connect(DB_PATH)
        self.create_tables()
        self.migrate_add_symbol_column()
    
    def create_tables(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                analyst_name TEXT,
                timeframe TEXT,
                symbol TEXT,
                signal_type TEXT,
                entry_price REAL,
                tp_price REAL,
                sl_price REAL,
                confidence INTEGER,
                result TEXT,
                closed_price REAL
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT,
                analyst_name TEXT,
                symbol TEXT,
                operation TEXT,
                entry_price REAL,
                exit_price REAL,
                result TEXT,
                profit_loss REAL,
                comment TEXT
            )
        ''')
        self.conn.commit()
    
    def migrate_add_symbol_column(self):
        cursor = self.conn.cursor()
        cursor.execute("PRAGMA table_info(signals)")
        columns = [col[1] for col in cursor.fetchall()]
        if 'symbol' not in columns:
            cursor.execute("ALTER TABLE signals ADD COLUMN symbol TEXT DEFAULT 'BTCUSDT'")
        cursor.execute("PRAGMA table_info(tickets)")
        columns = [col[1] for col in cursor.fetchall()]
        if 'symbol' not in columns:
            cursor.execute("ALTER TABLE tickets ADD COLUMN symbol TEXT DEFAULT 'BTCUSDT'")
        self.conn.commit()
    
    def save_signal(self, analyst_name, timeframe, signal_type, entry_price, tp_price, sl_price, confidence, symbol='BTCUSDT'):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO signals (timestamp, analyst_name, timeframe, symbol, signal_type, entry_price, tp_price, sl_price, confidence, result)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (datetime.now().isoformat(), analyst_name, timeframe, symbol, signal_type, entry_price, tp_price, sl_price, confidence, 'pending'))
        self.conn.commit()
        return cursor.lastrowid
    
    def update_signal_result(self, signal_id, result, closed_price):
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE signals SET result = ?, closed_price = ? WHERE id = ?
        ''', (result, closed_price, signal_id))
        self.conn.commit()
    
    def save_ticket(self, analyst_name, operation, entry_price, exit_price, result, profit_loss, comment='', symbol='BTCUSDT'):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO tickets (date, analyst_name, symbol, operation, entry_price, exit_price, result, profit_loss, comment)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (datetime.now().isoformat(), analyst_name, symbol, operation, entry_price, exit_price, result, profit_loss, comment))
        self.conn.commit()
    
    def get_signals_by_analyst(self, analyst_name, symbol=None):
        if symbol:
            query = "SELECT * FROM signals WHERE analyst_name = ? AND symbol = ? AND result != 'pending'"
            return pd.read_sql_query(query, self.conn, params=(analyst_name, symbol))
        else:
            query = "SELECT * FROM signals WHERE analyst_name = ? AND result != 'pending'"
            return pd.read_sql_query(query, self.conn, params=(analyst_name,))
    
    def get_all_tickets(self, symbol=None):
        if symbol:
            query = "SELECT * FROM tickets WHERE symbol = ?"
            return pd.read_sql_query(query, self.conn, params=(symbol,))
        else:
            return pd.read_sql_query("SELECT * FROM tickets", self.conn)
    
    def close(self):
        self.conn.close()