# analysts/analyst_1h.py
from .base_analyst import BaseAnalyst
import pandas as pd
import numpy as np
from ta.momentum import RSIIndicator
from ta.trend import MACD, EMAIndicator

class Analyst1H(BaseAnalyst):
    def __init__(self):
        super().__init__(timeframe='1h', name='Analyst_1H')
    
    def calculate_indicators(self):
        # Indicadores originales
        self.df['rsi'] = RSIIndicator(close=self.df['close'], window=14).rsi()
        macd = MACD(close=self.df['close'])
        self.df['macd'] = macd.macd()
        self.df['macd_signal'] = macd.macd_signal()
        self.df['macd_diff'] = macd.macd_diff()
        self.df['ema9'] = EMAIndicator(close=self.df['close'], window=9).ema_indicator()
        self.df['ema21'] = EMAIndicator(close=self.df['close'], window=21).ema_indicator()
        
        # Nuevos: Fibonacci (niveles basados en máximos y mínimos recientes)
        self.calculate_fibonacci()
        # Soporte y Resistencia dinámicos (pivotes)
        self.calculate_support_resistance()
        # Patrones de velas
        self.detect_candlestick_patterns()
    
    def calculate_fibonacci(self, lookback=100):
        """Calcula niveles de Fibonacci desde el máximo y mínimo del período"""
        df_window = self.df.iloc[-lookback:]
        high = df_window['high'].max()
        low = df_window['low'].min()
        diff = high - low
        self.fib_levels = {
            '0.236': low + 0.236 * diff,
            '0.382': low + 0.382 * diff,
            '0.5': low + 0.5 * diff,
            '0.618': low + 0.618 * diff,
            '0.786': low + 0.786 * diff,
            '1.0': high
        }
    
    def calculate_support_resistance(self, window=20):
        """Encuentra niveles de soporte/resistencia usando mínimos/máximos locales"""
        self.df['min_local'] = self.df['low'].rolling(window=window, center=True).apply(lambda x: x.iloc[window//2] if x.iloc[window//2] == x.min() else np.nan, raw=False)
        self.df['max_local'] = self.df['high'].rolling(window=window, center=True).apply(lambda x: x.iloc[window//2] if x.iloc[window//2] == x.max() else np.nan, raw=False)
        # Niveles recientes
        supports = self.df['min_local'].dropna().unique()[-5:]
        resistances = self.df['max_local'].dropna().unique()[-5:]
        self.near_support = any(abs(self.get_last_price() - s) / self.get_last_price() < 0.01 for s in supports)
        self.near_resistance = any(abs(self.get_last_price() - r) / self.get_last_price() < 0.01 for r in resistances)
    
    def detect_candlestick_patterns(self):
        """Detecta patrones en la última vela"""
        last = self.df.iloc[-1]
        body = abs(last['close'] - last['open'])
        upper_wick = last['high'] - max(last['close'], last['open'])
        lower_wick = min(last['close'], last['open']) - last['low']
        
        self.patterns = []
        # Doji (cuerpo muy pequeño)
        if body <= (last['high'] - last['low']) * 0.1:
            self.patterns.append('doji')
        # Martillo (cuerpo pequeño, mecha inferior larga)
        if lower_wick > 2 * body and upper_wick < body:
            self.patterns.append('hammer')
        # Engulfing (comparar con vela anterior)
        if len(self.df) >= 2:
            prev = self.df.iloc[-2]
            if prev['close'] < prev['open'] and last['close'] > last['open'] and last['open'] < prev['close'] and last['close'] > prev['open']:
                self.patterns.append('bullish_engulfing')
            if prev['close'] > prev['open'] and last['close'] < last['open'] and last['open'] > prev['close'] and last['close'] < prev['open']:
                self.patterns.append('bearish_engulfing')
    
    def generate_signal(self):
        if self.df is None or len(self.df) < 50:
            return {'signal': 'NEUTRAL', 'confidence': 0, 'entry_price': 0, 'tp_price': 0, 'sl_price': 0}
        
        last = self.df.iloc[-1]
        prev = self.df.iloc[-2]
        
        signal = 'NEUTRAL'
        confidence = 0
        reasons = []
        
        # Condiciones originales (RSI, MACD, EMA)
        buy_conditions = 0
        if last['rsi'] < 30:
            buy_conditions += 1
            reasons.append('RSI oversold')
        if last['macd'] > last['macd_signal'] and prev['macd'] <= prev['macd_signal']:
            buy_conditions += 1
            reasons.append('MACD bullish cross')
        if last['ema9'] > last['ema21']:
            buy_conditions += 1
            reasons.append('EMA9 above EMA21')
        
        sell_conditions = 0
        if last['rsi'] > 70:
            sell_conditions += 1
            reasons.append('RSI overbought')
        if last['macd'] < last['macd_signal'] and prev['macd'] >= prev['macd_signal']:
            sell_conditions += 1
            reasons.append('MACD bearish cross')
        if last['ema9'] < last['ema21']:
            sell_conditions += 1
            reasons.append('EMA9 below EMA21')
        
        # Nuevas condiciones por Fibonacci y S/R
        price = self.get_last_price()
        # Cercanía a Fibonacci 0.618 o 0.786 como soporte/resistencia
        if abs(price - self.fib_levels['0.618']) / price < 0.01:
            buy_conditions += 1
            reasons.append('Price near Fibonacci 0.618 support')
        if abs(price - self.fib_levels['0.382']) / price < 0.01:
            sell_conditions += 1
            reasons.append('Price near Fibonacci 0.382 resistance')
        
        # Soporte/resistencia dinámica
        if self.near_support:
            buy_conditions += 1
            reasons.append('Near dynamic support')
        if self.near_resistance:
            sell_conditions += 1
            reasons.append('Near dynamic resistance')
        
        # Patrones de velas
        if 'hammer' in self.patterns:
            buy_conditions += 1
            reasons.append('Hammer pattern')
        if 'bearish_engulfing' in self.patterns:
            sell_conditions += 1
            reasons.append('Bearish engulfing')
        if 'bullish_engulfing' in self.patterns:
            buy_conditions += 1
            reasons.append('Bullish engulfing')
        
        if buy_conditions >= 2:
            signal = 'BUY'
            confidence = min(100, buy_conditions * 20 + 10)
        elif sell_conditions >= 2:
            signal = 'SELL'
            confidence = min(100, sell_conditions * 20 + 10)
        else:
            signal = 'NEUTRAL'
            confidence = 30
        
        entry = self.get_last_price()
        atr = self.get_atr(14)
        if signal == 'BUY':
            tp = entry + (atr * 2)
            sl = entry - (atr * 1.5)
        elif signal == 'SELL':
            tp = entry - (atr * 2)
            sl = entry + (atr * 1.5)
        else:
            tp = entry
            sl = entry
        
        return {
            'signal': signal,
            'confidence': confidence,
            'entry_price': entry,
            'tp_price': tp,
            'sl_price': sl,
            'reasons': reasons,
            'fibonacci_levels': self.fib_levels,
            'patterns': self.patterns
        }