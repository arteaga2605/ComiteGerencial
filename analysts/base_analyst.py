# analysts/base_analyst.py
from abc import ABC, abstractmethod
import pandas as pd
import numpy as np

class BaseAnalyst(ABC):
    def __init__(self, timeframe, name):
        self.timeframe = timeframe
        self.name = name
        self.df = None
    
    def load_data(self, df):
        """Carga el DataFrame con velas"""
        self.df = df.copy()
        self.calculate_indicators()
    
    @abstractmethod
    def calculate_indicators(self):
        """Calcula los indicadores específicos del analista"""
        pass
    
    @abstractmethod
    def generate_signal(self):
        """
        Retorna un diccionario con:
        - signal: 'BUY', 'SELL', 'NEUTRAL'
        - confidence: 0-100
        - entry_price: float
        - tp_price: float
        - sl_price: float
        """
        pass
    
    def get_last_price(self):
        return self.df['close'].iloc[-1]
    
    def get_atr(self, period=14):
        """Average True Range para gestión de riesgo"""
        high = self.df['high']
        low = self.df['low']
        close = self.df['close']
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        return atr.iloc[-1]