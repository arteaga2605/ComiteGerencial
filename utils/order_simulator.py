# utils/order_simulator.py
import asyncio
import threading
import time
from datetime import datetime
import json
import websocket
from data.database import Database
from config import SYMBOL

class OrderSimulator:
    def __init__(self, symbol, entry, tp, sl, signal_type, analyst_name, confidence, timestamp=None):
        self.symbol = symbol
        self.entry = entry
        self.tp = tp
        self.sl = sl
        self.signal_type = signal_type  # 'BUY' or 'SELL'
        self.analyst_name = analyst_name
        self.confidence = confidence
        self.timestamp = timestamp or datetime.now().isoformat()
        self.status = 'open'  # open, closed_win, closed_loss
        self.exit_price = None
        self.db = Database()
        self.ws = None
        self.thread = None
        self.running = False
    
    def start_monitoring(self):
        """Inicia el monitoreo en un hilo separado con WebSocket"""
        self.running = True
        self.thread = threading.Thread(target=self._run_websocket)
        self.thread.daemon = True
        self.thread.start()
    
    def _run_websocket(self):
        """Conexión WebSocket para el símbolo específico"""
        stream_url = f"wss://stream.binance.com:9443/ws/{self.symbol.lower()}@trade"
        self.ws = websocket.WebSocketApp(stream_url,
                                         on_message=self._on_message,
                                         on_error=self._on_error,
                                         on_close=self._on_close)
        self.ws.run_forever()
    
    def _on_message(self, ws, message):
        if not self.running:
            return
        data = json.loads(message)
        price = float(data['p'])
        self._check_price(price)
    
    def _on_error(self, ws, error):
        print(f"WebSocket error para {self.symbol}: {error}")
    
    def _on_close(self, ws, close_status_code, close_msg):
        print(f"WebSocket cerrado para {self.symbol}")
        self.running = False
    
    def _check_price(self, current_price):
        """Verifica si se alcanzó TP o SL"""
        if self.status != 'open':
            return
        
        if self.signal_type == 'BUY':
            if current_price >= self.tp:
                self._close_order('win', self.tp)
            elif current_price <= self.sl:
                self._close_order('loss', self.sl)
        else:  # SELL
            if current_price <= self.tp:
                self._close_order('win', self.tp)
            elif current_price >= self.sl:
                self._close_order('loss', self.sl)
    
    def _close_order(self, result, exit_price):
        self.status = 'closed_' + result
        self.exit_price = exit_price
        profit_loss = self._calculate_pnl(exit_price)
        
        # Guardar ticket en base de datos
        self.db.save_ticket(
            analyst_name=self.analyst_name,
            operation=self.signal_type,
            entry_price=self.entry,
            exit_price=exit_price,
            result=result,
            profit_loss=profit_loss,
            comment=f'Automatic simulation | confianza {self.confidence}%',
            symbol=self.symbol
        )
        print(f"[SIM] Orden cerrada para {self.analyst_name} {self.symbol}: {result.upper()} a {exit_price} (PnL: {profit_loss:.2f})")
        self.stop()
    
    def _calculate_pnl(self, exit_price):
        if self.signal_type == 'BUY':
            return exit_price - self.entry
        else:
            return self.entry - exit_price
    
    def stop(self):
        self.running = False
        if self.ws:
            self.ws.close()

class SignalMonitor:
    """Monitorea señales y las simula automáticamente"""
    def __init__(self):
        self.active_orders = []  # lista de OrderSimulator activos
        self.db = Database()
    
    def add_signal(self, symbol, analyst_name, signal_type, entry, tp, sl, confidence):
        """Crea una orden simulada y la monitorea"""
        # Evitar duplicados de la misma señal (mismo analista, mismo símbolo, misma entrada)
        for order in self.active_orders:
            if (order.symbol == symbol and order.analyst_name == analyst_name and 
                order.entry == entry and order.status == 'open'):
                print(f"[SIM] Señal duplicada ignorada para {analyst_name} {symbol}")
                return
        
        sim = OrderSimulator(symbol, entry, tp, sl, signal_type, analyst_name, confidence)
        sim.start_monitoring()
        self.active_orders.append(sim)
        print(f"[SIM] Nueva orden simulada para {analyst_name} {symbol}: {signal_type} entrada {entry} TP {tp} SL {sl}")
    
    def stop_all(self):
        for order in self.active_orders:
            order.stop()
        self.active_orders.clear()