# analysts/analyst_1d.py
from .base_analyst import BaseAnalyst
import pandas as pd
import numpy as np
from ta.trend import IchimokuIndicator, ADXIndicator, CCIIndicator
from ta.volume import OnBalanceVolumeIndicator, ChaikinMoneyFlowIndicator

class Analyst1D(BaseAnalyst):
    def __init__(self):
        super().__init__(timeframe='1d', name='Analyst_1D')
    
    def calculate_indicators(self):
        # Ichimoku (conversion=9, base=26, span=52)
        ichi = IchimokuIndicator(high=self.df['high'], low=self.df['low'], window1=9, window2=26, window3=52)
        self.df['ichimoku_a'] = ichi.ichimoku_a()
        self.df['ichimoku_b'] = ichi.ichimoku_b()
        self.df['ichimoku_base'] = ichi.ichimoku_base_line()
        self.df['ichimoku_conversion'] = ichi.ichimoku_conversion_line()
        
        # ADX (14)
        adx = ADXIndicator(high=self.df['high'], low=self.df['low'], close=self.df['close'], window=14)
        self.df['adx'] = adx.adx()
        self.df['plus_di'] = adx.adx_pos()
        self.df['minus_di'] = adx.adx_neg()
        
        # CCI (20)
        cci = CCIIndicator(high=self.df['high'], low=self.df['low'], close=self.df['close'], window=20)
        self.df['cci'] = cci.cci()
        
        # OBV (On Balance Volume)
        obv = OnBalanceVolumeIndicator(close=self.df['close'], volume=self.df['volume'])
        self.df['obv'] = obv.on_balance_volume()
        self.df['obv_sma'] = self.df['obv'].rolling(window=20).mean()
        self.df['obv_trend'] = self.df['obv'] - self.df['obv_sma']  # positivo = acumulación
        
        # CMF (Chaikin Money Flow)
        cmf = ChaikinMoneyFlowIndicator(high=self.df['high'], low=self.df['low'], close=self.df['close'], volume=self.df['volume'], window=20)
        self.df['cmf'] = cmf.chaikin_money_flow()
    
    def generate_signal(self):
        if self.df is None or len(self.df) < 60:
            return {'signal': 'NEUTRAL', 'confidence': 0, 'entry_price': 0, 'tp_price': 0, 'sl_price': 0}
        
        last = self.df.iloc[-1]
        
        signal = 'NEUTRAL'
        confidence = 0
        reasons = []
        
        # Tendencia según Ichimoku: precio > nube es bullish
        price_above_cloud = last['close'] > max(last['ichimoku_a'], last['ichimoku_b'])
        price_below_cloud = last['close'] < min(last['ichimoku_a'], last['ichimoku_b'])
        
        buy_conditions = 0
        if price_above_cloud:
            buy_conditions += 1
            reasons.append('Price above Ichimoku cloud')
        if last['adx'] > 25 and last['plus_di'] > last['minus_di']:
            buy_conditions += 1
            reasons.append('ADX strong uptrend')
        if last['cci'] > 100:
            buy_conditions += 1
            reasons.append('CCI bullish')
        # Indicadores de volumen
        if last['obv_trend'] > 0:
            buy_conditions += 1
            reasons.append('OBV accumulation')
        if last['cmf'] > 0.1:
            buy_conditions += 1
            reasons.append('CMF buying pressure')
        
        sell_conditions = 0
        if price_below_cloud:
            sell_conditions += 1
            reasons.append('Price below Ichimoku cloud')
        if last['adx'] > 25 and last['minus_di'] > last['plus_di']:
            sell_conditions += 1
            reasons.append('ADX strong downtrend')
        if last['cci'] < -100:
            sell_conditions += 1
            reasons.append('CCI bearish')
        if last['obv_trend'] < 0:
            sell_conditions += 1
            reasons.append('OBV distribution')
        if last['cmf'] < -0.1:
            sell_conditions += 1
            reasons.append('CMF selling pressure')
        
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
            tp = entry + (atr * 3)
            sl = entry - (atr * 2)
        elif signal == 'SELL':
            tp = entry - (atr * 3)
            sl = entry + (atr * 2)
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