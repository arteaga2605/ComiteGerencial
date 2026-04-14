# analysts/gem_hunter.py
import pandas as pd
import numpy as np
import sys
from data.binance_client import BinanceClient
from config import GEM_HUNTER
from ta.momentum import RSIIndicator
from ta.trend import SMAIndicator, MACD
from ta.volume import VolumeWeightedAveragePrice
from utils.telegram_notifier import TelegramNotifier

class GemHunter:
    def __init__(self):
        self.name = "GemHunter"
        self.client = BinanceClient()
        self.results = []
    
    def get_all_usdt_pairs(self):
        endpoint = f"{self.client.BASE_URL}/exchangeInfo"
        try:
            import requests
            resp = requests.get(endpoint)
            data = resp.json()
            symbols = [s['symbol'] for s in data['symbols'] if s['symbol'].endswith('USDT') and s['status'] == 'TRADING']
            return symbols[:GEM_HUNTER['max_pairs']]
        except:
            return []
    
    def get_24h_ticker(self, symbol):
        endpoint = f"{self.client.BASE_URL}/ticker/24hr"
        try:
            import requests
            resp = requests.get(endpoint, params={'symbol': symbol})
            data = resp.json()
            return {
                'volume': float(data['quoteVolume']),
                'price_change_percent': float(data['priceChangePercent']),
                'last_price': float(data['lastPrice'])
            }
        except:
            return None
    
    def analyze_pair(self, symbol):
        df = self.client.get_klines(symbol, '1d', limit=200)
        if df.empty or len(df) < 50:
            return None
        
        close = df['close']
        rsi = RSIIndicator(close=close, window=14).rsi().iloc[-1]
        sma50 = SMAIndicator(close=close, window=50).sma_indicator().iloc[-1]
        sma200 = SMAIndicator(close=close, window=200).sma_indicator().iloc[-1]
        macd = MACD(close=close)
        macd_diff = macd.macd_diff().iloc[-1]
        
        vol_sma = df['volume'].rolling(20).mean().iloc[-1]
        vol_ratio = df['volume'].iloc[-1] / vol_sma if vol_sma != 0 else 1
        
        ticker = self.get_24h_ticker(symbol)
        if not ticker:
            return None
        volume_usdt = ticker['volume']
        price_change = ticker['price_change_percent']
        last_price = ticker['last_price']
        
        if volume_usdt < GEM_HUNTER['min_volume_usdt_24h']:
            return None
        
        score = 0
        
        if last_price < 1:
            score += 15
        elif last_price < 5:
            score += 10
        elif last_price < 10:
            score += 5
        
        if rsi < 30:
            score += 20
        elif rsi < 40:
            score += 10
        
        if last_price < sma200:
            score += 15
        elif last_price < sma50:
            score += 5
        
        if macd_diff > 0:
            score += 10
        
        if vol_ratio > 1.2:
            score += 15
        elif vol_ratio > 1:
            score += 5
        
        if -20 < price_change < -5:
            score += 10
        elif -5 <= price_change < 0:
            score += 5
        
        if volume_usdt > 10_000_000:
            score += 10
        elif volume_usdt > 5_000_000:
            score += 5
        
        best_tf = '1d'
        if score > 70:
            best_tf = '4h'
        elif score > 60:
            best_tf = '1d'
        else:
            best_tf = '1h'
        
        df_tf = self.client.get_klines(symbol, best_tf, limit=100)
        if df_tf.empty:
            atr = last_price * 0.05
        else:
            high = df_tf['high']
            low = df_tf['low']
            close_tf = df_tf['close']
            tr1 = high - low
            tr2 = abs(high - close_tf.shift())
            tr3 = abs(low - close_tf.shift())
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            atr = tr.rolling(14).mean().iloc[-1]
            if pd.isna(atr):
                atr = last_price * 0.05
        
        entry = last_price
        tp = entry + (atr * 2.5)
        sl = entry - (atr * 1.5)
        
        estimated_accuracy = min(90, score * 0.8 + 20)
        
        return {
            'symbol': symbol,
            'operation': 'LONG',
            'score': round(score, 1),
            'estimated_accuracy': round(estimated_accuracy, 1),
            'current_price': round(entry, 8),
            'suggested_timeframe': best_tf,
            'tp': round(tp, 8),
            'sl': round(sl, 8),
            'volume_usdt': volume_usdt,
            'price_change_24h': price_change,
            'rsi': round(rsi, 1)
        }
    
    def find_gems(self):
        print("[BUSQUEDA] Buscando gemas ocultas en Binance... (puede tomar unos segundos)")
        all_pairs = self.get_all_usdt_pairs()
        if not all_pairs:
            print("[ERROR] No se pudieron obtener pares. Verifica conexion.")
            return []
        
        results = []
        total = len(all_pairs)
        for i, sym in enumerate(all_pairs):
            print(f"Analizando {sym} ({i+1}/{total})", end='\r')
            analysis = self.analyze_pair(sym)
            if analysis and analysis['score'] >= GEM_HUNTER['min_score']:
                results.append(analysis)
        
        print("\n[OK] Analisis completado.")
        results.sort(key=lambda x: x['score'], reverse=True)
        return results[:GEM_HUNTER['max_results']]
    
    def print_gems(self, gems):
        if not gems:
            print("[INFO] No se encontraron gemas que cumplan los criterios.")
            return
        print("\n" + "="*80)
        print("TOP {} GEMAS ENCONTRADAS".format(len(gems)))
        print("="*80)
        for idx, g in enumerate(gems, 1):
            print("\n{}. {} | Score: {} | Acierto estimado: {}%".format(idx, g['symbol'], g['score'], g['estimated_accuracy']))
            print("   Operacion sugerida: {} (solo compra)".format(g['operation']))
            print("   Precio actual: {} USDT | Cambio 24h: {}%".format(g['current_price'], g['price_change_24h']))
            print("   RSI: {} | Volumen 24h: ${:,.0f} USDT".format(g['rsi'], g['volume_usdt']))
            print("   Temporalidad sugerida: {}".format(g['suggested_timeframe']))
            print("   [TP] Take Profit: {} | [SL] Stop Loss: {}".format(g['tp'], g['sl']))
        print("="*80)
    
    def run(self):
        gems = self.find_gems()
        self.print_gems(gems)
        from data.database import Database
        db = Database()
        for g in gems:
            db.save_signal(
                analyst_name=self.name,
                timeframe=g['suggested_timeframe'],
                signal_type='BUY',
                entry_price=g['current_price'],
                tp_price=g['tp'],
                sl_price=g['sl'],
                confidence=g['estimated_accuracy'],
                symbol=g['symbol']
            )
        db.close()
        
        notifier = TelegramNotifier()
        if gems:
            for g in gems:
                notifier.send_signal(
                    analyst_name=self.name,
                    symbol=g['symbol'],
                    signal_type='BUY',
                    entry=g['current_price'],
                    tp=g['tp'],
                    sl=g['sl'],
                    confidence=g['estimated_accuracy'],
                    extra_info="Score: {} | Timeframe: {} | Vol: ${:,.0f}".format(g['score'], g['suggested_timeframe'], g['volume_usdt'])
                )
        else:
            notifier.send_message("Caza de gemas: No se encontraron oportunidades.")
        
        return gems