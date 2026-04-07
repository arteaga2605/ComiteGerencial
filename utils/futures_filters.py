# utils/futures_filters.py
from data.binance_client import BinanceClient
from config import FUTURES_FUNDING_RATE_THRESHOLD

class FuturesFilters:
    def __init__(self, symbol):
        self.symbol = symbol
        self.client = BinanceClient()
    
    def funding_rate_filter(self, signal_type):
        """
        signal_type: 'BUY' o 'SELL'
        Retorna (bool, mensaje) indicando si está permitido según funding rate.
        """
        fr = self.client.get_funding_rate(self.symbol)
        if signal_type == 'BUY' and fr > FUTURES_FUNDING_RATE_THRESHOLD:
            return False, f"Funding rate muy positivo ({fr:.4%}) -> evitar LONG"
        if signal_type == 'SELL' and fr < -FUTURES_FUNDING_RATE_THRESHOLD:
            return False, f"Funding rate muy negativo ({fr:.4%}) -> evitar SHORT"
        return True, f"Funding rate {fr:.4%} aceptable"
    
    def liquidation_cascade_filter(self):
        """
        Analiza liquidaciones recientes para detectar cascada.
        Retorna (bool, mensaje) si hay riesgo alto.
        """
        liquidations = self.client.get_liquidations(self.symbol, limit=50)
        if not liquidations:
            return True, "Sin datos de liquidaciones"
        
        # Contar liquidaciones en última hora
        now = pd.Timestamp.now(tz='UTC')
        recent = 0
        for liq in liquidations:
            time_str = liq.get('time')
            if time_str:
                liq_time = pd.to_datetime(time_str, unit='ms', utc=True)
                if (now - liq_time).total_seconds() < 3600:
                    recent += 1
        if recent > 10:
            return False, f"Alta actividad de liquidaciones ({recent} en última hora) -> posible cascada"
        return True, f"Liquidaciones normales ({recent} en última hora)"
    
    def order_book_imbalance(self, depth=10):
        """Retorna imbalance (positivo = presión compradora)"""
        book = self.client.get_order_book(self.symbol, limit=depth)
        return self.client.compute_order_book_imbalance(book, depth)