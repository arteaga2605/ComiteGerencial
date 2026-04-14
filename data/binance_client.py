# data/binance_client.py
import requests
import pandas as pd
from datetime import datetime
import time

class BinanceClient:
    BASE_URL = 'https://api.binance.com/api/v3'
    FUTURES_BASE_URL = 'https://fapi.binance.com/fapi/v1'
    
    @staticmethod
    def get_klines(symbol, interval, limit=200):
        """
        Obtiene velas históricas sin API key.
        Retorna DataFrame con columnas: timestamp, open, high, low, close, volume
        """
        endpoint = f"{BinanceClient.BASE_URL}/klines"
        params = {
            'symbol': symbol,
            'interval': interval,
            'limit': limit
        }
        try:
            response = requests.get(endpoint, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            df = pd.DataFrame(data, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_asset_volume', 'number_of_trades',
                'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
            ])
            
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = df[col].astype(float)
            
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
            return df
        except Exception as e:
            # No imprimir error para no saturar consola, pero se puede activar en debug
            # print(f"Error obteniendo velas {symbol} {interval}: {e}")
            return pd.DataFrame()
    
    @staticmethod
    def get_funding_rate(symbol):
        """Obtiene tasa de funding actual para futuros (público)"""
        endpoint = f"{BinanceClient.FUTURES_BASE_URL}/premiumIndex"
        params = {'symbol': symbol}
        try:
            resp = requests.get(endpoint, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            return float(data.get('lastFundingRate', 0))
        except:
            return 0.0
    
    @staticmethod
    def get_order_book(symbol, limit=20):
        """Obtiene profundidad de mercado (order book)"""
        endpoint = f"{BinanceClient.BASE_URL}/depth"
        params = {'symbol': symbol, 'limit': limit}
        try:
            resp = requests.get(endpoint, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            bids = [[float(price), float(qty)] for price, qty in data['bids']]
            asks = [[float(price), float(qty)] for price, qty in data['asks']]
            return {'bids': bids, 'asks': asks}
        except:
            return {'bids': [], 'asks': []}
    
    @staticmethod
    def get_liquidations(symbol, limit=100):
        """Obtiene liquidaciones recientes en futuros (endpoint público)"""
        endpoint = f"{BinanceClient.FUTURES_BASE_URL}/forceOrders"
        params = {'symbol': symbol, 'limit': limit}
        try:
            resp = requests.get(endpoint, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            return data.get('forceOrders', [])
        except:
            return []
    
    @staticmethod
    def compute_order_book_imbalance(book, depth=10):
        """Calcula imbalance: (volumen_bids - volumen_asks) / (volumen_total)"""
        bids_vol = sum([bid[1] for bid in book['bids'][:depth]])
        asks_vol = sum([ask[1] for ask in book['asks'][:depth]])
        total = bids_vol + asks_vol
        if total == 0:
            return 0
        return (bids_vol - asks_vol) / total