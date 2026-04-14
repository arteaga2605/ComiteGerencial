# utils/auto_validator.py
import time
import threading
from datetime import datetime, timedelta
import sqlite3
from data.binance_client import BinanceClient
from config import AUTO_VALIDATION, DB_PATH

class AutoValidator:
    def __init__(self):
        self.client = BinanceClient()
        self.running = False
        self.thread = None
        # No crear conexión aquí, se creará en el hilo
    
    def start(self):
        """Inicia el hilo de validación automática"""
        if not AUTO_VALIDATION['enabled']:
            print("Validación automática deshabilitada en config.py")
            return
        self.running = True
        self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.thread.start()
        print(f"✅ Validador automático iniciado (revisa cada {AUTO_VALIDATION['check_interval_seconds']}s)")
    
    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)
    
    def _get_db_connection(self):
        """Crea una conexión nueva para el hilo actual"""
        return sqlite3.connect(DB_PATH, check_same_thread=False)
    
    def _monitor_loop(self):
        while self.running:
            try:
                self._check_pending_signals()
            except Exception as e:
                print(f"Error en validación automática: {e}")
            time.sleep(AUTO_VALIDATION['check_interval_seconds'])
    
    def _check_pending_signals(self):
        """Busca señales pendientes en la BD y verifica si alcanzaron TP o SL"""
        conn = self._get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                SELECT id, analyst_name, symbol, signal_type, entry_price, tp_price, sl_price, timestamp
                FROM signals
                WHERE result = 'pending'
            ''')
            pending = cursor.fetchall()
            
            for sig in pending:
                sig_id, analyst, symbol, signal_type, entry, tp, sl, timestamp_str = sig
                timestamp = datetime.fromisoformat(timestamp_str)
                # Si pasó más de max_wait_hours, cerrar como pérdida por tiempo
                if datetime.now() - timestamp > timedelta(hours=AUTO_VALIDATION['max_wait_hours']):
                    self._close_signal(conn, sig_id, analyst, symbol, signal_type, entry, 'loss', None, "Tiempo de espera agotado")
                    continue
                
                # Obtener precio actual del símbolo (último close de vela 1m)
                df = self.client.get_klines(symbol, '1m', limit=1)
                if df.empty:
                    continue
                current_price = df['close'].iloc[-1]
                
                reached_tp = False
                reached_sl = False
                if signal_type == 'BUY':
                    if current_price >= tp:
                        reached_tp = True
                    elif current_price <= sl:
                        reached_sl = True
                else:  # SELL
                    if current_price <= tp:
                        reached_tp = True
                    elif current_price >= sl:
                        reached_sl = True
                
                if reached_tp:
                    self._close_signal(conn, sig_id, analyst, symbol, signal_type, entry, 'win', tp, "TP alcanzado")
                elif reached_sl:
                    self._close_signal(conn, sig_id, analyst, symbol, signal_type, entry, 'loss', sl, "SL alcanzado")
        finally:
            conn.close()
    
    def _close_signal(self, conn, signal_id, analyst, symbol, signal_type, entry_price, result, close_price, comment):
        """Cierra una señal y crea un ticket automático (usa la conexión pasada)"""
        if close_price is None:
            df = self.client.get_klines(symbol, '1m', limit=1)
            close_price = df['close'].iloc[-1] if not df.empty else entry_price
        
        if signal_type == 'BUY':
            pnl = close_price - entry_price
        else:
            pnl = entry_price - close_price
        
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE signals SET result = ?, closed_price = ? WHERE id = ?
        ''', (result, close_price, signal_id))
        
        cursor.execute('''
            INSERT INTO tickets (date, analyst_name, symbol, operation, entry_price, exit_price, result, profit_loss, comment)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (datetime.now().isoformat(), analyst, symbol, signal_type, entry_price, close_price, result, pnl, f"Auto: {comment}"))
        
        conn.commit()
        print(f"🔔 {analyst} | {symbol} | {signal_type} | {result.upper()} | PnL: {pnl:.2f} | {comment}")