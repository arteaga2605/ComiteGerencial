# analysts/analyst_1m.py
from .base_analyst import BaseAnalyst
import pandas as pd
import numpy as np
from ta.trend import SMAIndicator
from ta.momentum import RSIIndicator

class Analyst1M(BaseAnalyst):
    def __init__(self):
        super().__init__(timeframe='1M', name='Analyst_1M')
    
    def calculate_indicators(self):
        # SMA 50 y 200
        self.df['sma50'] = SMAIndicator(close=self.df['close'], window=50).sma_indicator()
        self.df['sma200'] = SMAIndicator(close=self.df['close'], window=200).sma_indicator()
        # RSI 14
        self.df['rsi'] = RSIIndicator(close=self.df['close'], window=14).rsi()
        # Tendencia de precio (máximos y mínimos)
        self.df['higher_high'] = self.df['high'] > self.df['high'].shift(1).rolling(window=20).max()
        self.df['lower_low'] = self.df['low'] < self.df['low'].shift(1).rolling(window=20).min()
    
    def generate_signal(self):
        # Verificar datos suficientes (mínimo 100 velas para SMA50)
        if self.df is None or len(self.df) < 100:
            print(f"⚠️ {self.name}: Datos insuficientes ({len(self.df) if self.df is not None else 0} velas). Se necesita al menos 100.")
            # Devolver señal NEUTRAL pero con TP/SL basados en precio actual y ATR estimado
            entry = self.get_last_price() if self.df is not None and len(self.df) > 0 else 50000
            atr_est = entry * 0.02  # ATR estimado 2%
            return {
                'signal': 'NEUTRAL',
                'confidence': 0,
                'entry_price': entry,
                'tp_price': entry + atr_est * 2,
                'sl_price': entry - atr_est * 1.5,
                'reasons': ['Datos insuficientes']
            }
        
        last = self.df.iloc[-1]
        prev = self.df.iloc[-2] if len(self.df) > 1 else last
        
        signal = 'NEUTRAL'
        confidence = 0
        reasons = []
        
        buy_conditions = 0
        # Precio por encima de SMA200 (tendencia alcista larga)
        if not pd.isna(last['sma200']) and last['close'] > last['sma200']:
            buy_conditions += 1
            reasons.append('Price above SMA200')
        # Cruce dorado: SMA50 > SMA200
        if not pd.isna(last['sma50']) and not pd.isna(last['sma200']):
            if last['sma50'] > last['sma200'] and prev['sma50'] <= prev['sma200']:
                buy_conditions += 1
                reasons.append('Golden cross SMA50/200')
        # RSI entre 30 y 70 (sin sobrecompra)
        if not pd.isna(last['rsi']) and 30 < last['rsi'] < 70:
            buy_conditions += 1
            reasons.append('RSI neutral-bullish')
        
        sell_conditions = 0
        if not pd.isna(last['sma200']) and last['close'] < last['sma200']:
            sell_conditions += 1
            reasons.append('Price below SMA200')
        if not pd.isna(last['sma50']) and not pd.isna(last['sma200']):
            if last['sma50'] < last['sma200'] and prev['sma50'] >= prev['sma200']:
                sell_conditions += 1
                reasons.append('Death cross SMA50/200')
        if not pd.isna(last['rsi']) and last['rsi'] > 70:
            sell_conditions += 1
            reasons.append('RSI overbought')
        
        if buy_conditions >= 2:
            signal = 'BUY'
            confidence = min(100, buy_conditions * 30 + 10)
        elif sell_conditions >= 2:
            signal = 'SELL'
            confidence = min(100, sell_conditions * 30 + 10)
        else:
            signal = 'NEUTRAL'
            confidence = 30
            reasons.append('No hay suficientes condiciones')
        
        entry = self.get_last_price()
        atr = self.get_atr(14) if not pd.isna(self.get_atr(14)) else entry * 0.02
        if signal == 'BUY':
            tp = entry + (atr * 4)
            sl = entry - (atr * 2.5)
        elif signal == 'SELL':
            tp = entry - (atr * 4)
            sl = entry + (atr * 2.5)
        else:
            # Para NEUTRAL, dar niveles de referencia (no se usarán para operar)
            tp = entry + (atr * 2)
            sl = entry - (atr * 1.5)
        
        return {
            'signal': signal,
            'confidence': confidence,
            'entry_price': round(entry, 2),
            'tp_price': round(tp, 2),
            'sl_price': round(sl, 2),
            'reasons': reasons
        }