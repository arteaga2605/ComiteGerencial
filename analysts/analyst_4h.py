# analysts/analyst_4h.py
from .base_analyst import BaseAnalyst
import pandas as pd
import numpy as np
from ta.volatility import BollingerBands
from ta.momentum import StochasticOscillator
from ta.volume import VolumeWeightedAveragePrice, OnBalanceVolumeIndicator, ChaikinMoneyFlowIndicator

class Analyst4H(BaseAnalyst):
    def __init__(self):
        super().__init__(timeframe='4h', name='Analyst_4H')
    
    def calculate_indicators(self):
        # Originales
        bb = BollingerBands(close=self.df['close'], window=20, window_dev=2)
        self.df['bb_upper'] = bb.bollinger_hband()
        self.df['bb_middle'] = bb.bollinger_mavg()
        self.df['bb_lower'] = bb.bollinger_lband()
        self.df['bb_width'] = (self.df['bb_upper'] - self.df['bb_lower']) / self.df['bb_middle']
        stoch = StochasticOscillator(high=self.df['high'], low=self.df['low'], close=self.df['close'], window=14, smooth_window=3)
        self.df['stoch_k'] = stoch.stoch()
        self.df['stoch_d'] = stoch.stoch_signal()
        self.df['vwap'] = VolumeWeightedAveragePrice(high=self.df['high'], low=self.df['low'], close=self.df['close'], volume=self.df['volume']).volume_weighted_average_price()
        self.df['volume_sma'] = self.df['volume'].rolling(window=20).mean()
        self.df['volume_ratio'] = self.df['volume'] / self.df['volume_sma']
        
        # Nuevos indicadores de volumen
        obv = OnBalanceVolumeIndicator(close=self.df['close'], volume=self.df['volume'])
        self.df['obv'] = obv.on_balance_volume()
        self.df['obv_sma'] = self.df['obv'].rolling(window=20).mean()
        self.df['obv_trend'] = self.df['obv'] - self.df['obv_sma']  # positivo = acumulación
        
        cmf = ChaikinMoneyFlowIndicator(high=self.df['high'], low=self.df['low'], close=self.df['close'], volume=self.df['volume'], window=20)
        self.df['cmf'] = cmf.chaikin_money_flow()
    
    def generate_signal(self):
        if self.df is None or len(self.df) < 50:
            return {'signal': 'NEUTRAL', 'confidence': 0, 'entry_price': 0, 'tp_price': 0, 'sl_price': 0}
        
        last = self.df.iloc[-1]
        prev = self.df.iloc[-2]
        
        signal = 'NEUTRAL'
        confidence = 0
        reasons = []
        
        buy_conditions = 0
        if last['close'] <= last['bb_lower'] * 1.01:
            buy_conditions += 1
            reasons.append('Price near lower BB')
        if last['stoch_k'] < 20 and last['stoch_k'] > last['stoch_d'] and prev['stoch_k'] <= prev['stoch_d']:
            buy_conditions += 1
            reasons.append('Stoch oversold bullish cross')
        if last['volume_ratio'] > 1.2:
            buy_conditions += 1
            reasons.append('High volume')
        
        # Nuevas condiciones de volumen
        if last['obv_trend'] > 0:
            buy_conditions += 1
            reasons.append('OBV positive trend (accumulation)')
        if last['cmf'] > 0.1:
            buy_conditions += 1
            reasons.append('CMF > 0.1 (buying pressure)')
        
        sell_conditions = 0
        if last['close'] >= last['bb_upper'] * 0.99:
            sell_conditions += 1
            reasons.append('Price near upper BB')
        if last['stoch_k'] > 80 and last['stoch_k'] < last['stoch_d'] and prev['stoch_k'] >= prev['stoch_d']:
            sell_conditions += 1
            reasons.append('Stoch overbought bearish cross')
        if last['volume_ratio'] > 1.2:
            sell_conditions += 1
            reasons.append('High volume')
        if last['obv_trend'] < 0:
            sell_conditions += 1
            reasons.append('OBV negative trend (distribution)')
        if last['cmf'] < -0.1:
            sell_conditions += 1
            reasons.append('CMF < -0.1 (selling pressure)')
        
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
            tp = entry + (atr * 2.5)
            sl = entry - (atr * 1.5)
        elif signal == 'SELL':
            tp = entry - (atr * 2.5)
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
            'obv': last['obv'],
            'cmf': last['cmf']
        }