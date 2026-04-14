# analysts/smc_analyst.py
import pandas as pd
import numpy as np
from data.binance_client import BinanceClient
from config import SMC_STRATEGY
from utils.telegram_notifier import TelegramNotifier

class SMCAnalyst:
    def __init__(self, symbol):
        self.name = "SMC_Analyst"
        self.symbol = symbol
        self.client = BinanceClient()
        self.tf_analysis = SMC_STRATEGY['timeframe_analysis']
        self.tf_entry = SMC_STRATEGY['timeframe_entry']
        self.tp_percent = SMC_STRATEGY['tp_percent'] / 100
        self.sl_percent = SMC_STRATEGY['sl_percent'] / 100
        self.capital = SMC_STRATEGY['capital_usd']
        self.leverage = SMC_STRATEGY['leverage']
    
    def get_support_resistance_monthly(self):
        df = self.client.get_klines(self.symbol, self.tf_analysis, limit=100)
        if df.empty:
            return [], []
        df['max_local'] = df['high'].rolling(window=5, center=True).max()
        df['min_local'] = df['low'].rolling(window=5, center=True).min()
        resistances = df[df['high'] == df['max_local']]['high'].dropna().unique()[-5:]
        supports = df[df['low'] == df['min_local']]['low'].dropna().unique()[-5:]
        return supports, resistances
    
    def get_fibonacci_levels(self):
        df = self.client.get_klines(self.symbol, self.tf_analysis, limit=200)
        if df.empty:
            return {}
        recent = df.iloc[-50:]
        high = recent['high'].max()
        low = recent['low'].min()
        diff = high - low
        fib_levels = {
            '0.236': low + 0.236 * diff,
            '0.382': low + 0.382 * diff,
            '0.5': low + 0.5 * diff,
            '0.618': low + 0.618 * diff,
            '0.786': low + 0.786 * diff,
            '1.0': high
        }
        return fib_levels
    
    def get_volume_confirmation(self):
        df = self.client.get_klines(self.symbol, self.tf_entry, limit=50)
        if df.empty:
            return 1.0
        last_vol = df['volume'].iloc[-1]
        avg_vol = df['volume'].rolling(20).mean().iloc[-1]
        return last_vol / avg_vol if avg_vol != 0 else 1.0
    
    def detect_candle_pattern(self):
        df = self.client.get_klines(self.symbol, self.tf_entry, limit=5)
        if df.empty or len(df) < 2:
            return None
        last = df.iloc[-1]
        prev = df.iloc[-2]
        body = abs(last['close'] - last['open'])
        upper_wick = last['high'] - max(last['close'], last['open'])
        lower_wick = min(last['close'], last['open']) - last['low']
        
        if body <= (last['high'] - last['low']) * 0.1:
            return 'doji'
        if lower_wick > 2 * body and upper_wick < body and last['close'] > last['open']:
            return 'hammer_bullish'
        if upper_wick > 2 * body and lower_wick < body and last['close'] > last['open']:
            return 'inverted_hammer'
        if prev['close'] < prev['open'] and last['close'] > last['open'] and last['open'] < prev['close'] and last['close'] > prev['open']:
            return 'bullish_engulfing'
        if prev['close'] > prev['open'] and last['close'] < last['open'] and last['open'] > prev['close'] and last['close'] < prev['open']:
            return 'bearish_engulfing'
        return None
    
    def analyze(self):
        supports, resistances = self.get_support_resistance_monthly()
        fib = self.get_fibonacci_levels()
        df_price = self.client.get_klines(self.symbol, self.tf_entry, limit=1)
        if df_price.empty:
            return {'signal': 'NEUTRAL', 'confidence': 0, 'entry_price': 0, 'tp_price': 0, 'sl_price': 0, 'reasons': ['Sin datos']}
        current_price = df_price['close'].iloc[-1]
        vol_ratio = self.get_volume_confirmation()
        pattern = self.detect_candle_pattern()
        
        nearest_support = min(supports, key=lambda x: abs(current_price - x)) if len(supports) > 0 else None
        nearest_resistance = min(resistances, key=lambda x: abs(current_price - x)) if len(resistances) > 0 else None
        nearest_fib = min(fib.items(), key=lambda x: abs(current_price - x[1])) if fib else None
        
        signal = 'NEUTRAL'
        confidence = 0
        reasons = []
        
        long_conditions = 0
        if nearest_support and current_price <= nearest_support * 1.02:
            long_conditions += 1
            reasons.append(f"Cerca de soporte mensual {nearest_support:.2f}")
        if nearest_fib and nearest_fib[0] in ['0.618', '0.786'] and current_price <= nearest_fib[1] * 1.01:
            long_conditions += 1
            reasons.append(f"Cerca de Fibonacci {nearest_fib[0]} ({nearest_fib[1]:.2f})")
        if vol_ratio > 1.2:
            long_conditions += 1
            reasons.append(f"Volumen alto (ratio {vol_ratio:.2f})")
        if pattern in ['hammer_bullish', 'bullish_engulfing', 'inverted_hammer']:
            long_conditions += 1
            reasons.append(f"Patron alcista: {pattern}")
        
        short_conditions = 0
        if nearest_resistance and current_price >= nearest_resistance * 0.98:
            short_conditions += 1
            reasons.append(f"Cerca de resistencia mensual {nearest_resistance:.2f}")
        if nearest_fib and nearest_fib[0] in ['0.236', '0.382'] and current_price >= nearest_fib[1] * 0.99:
            short_conditions += 1
            reasons.append(f"Cerca de Fibonacci {nearest_fib[0]} ({nearest_fib[1]:.2f})")
        if vol_ratio > 1.2:
            short_conditions += 1
            reasons.append(f"Volumen alto (ratio {vol_ratio:.2f})")
        if pattern == 'bearish_engulfing':
            short_conditions += 1
            reasons.append(f"Patron bajista: {pattern}")
        
        if long_conditions >= 2:
            signal = 'BUY'
            confidence = min(90, long_conditions * 30 + 10)
        elif short_conditions >= 2:
            signal = 'SELL'
            confidence = min(90, short_conditions * 30 + 10)
        
        entry = current_price
        if signal == 'BUY':
            tp = entry * (1 + self.tp_percent)
            sl = entry * (1 - self.sl_percent)
        elif signal == 'SELL':
            tp = entry * (1 - self.tp_percent)
            sl = entry * (1 + self.sl_percent)
        else:
            tp = entry
            sl = entry
        
        position_size = self.capital * self.leverage
        profit_usd = position_size * self.tp_percent if signal != 'NEUTRAL' else 0
        loss_usd = position_size * self.sl_percent if signal != 'NEUTRAL' else 0
        
        return {
            'signal': signal,
            'confidence': confidence,
            'entry_price': round(entry, 8),
            'tp_price': round(tp, 8),
            'sl_price': round(sl, 8),
            'tp_percent': self.tp_percent * 100,
            'sl_percent': self.sl_percent * 100,
            'leverage': self.leverage,
            'capital_usd': self.capital,
            'position_size_usd': position_size,
            'profit_if_win_usd': round(profit_usd, 2),
            'loss_if_loss_usd': round(loss_usd, 2),
            'reasons': reasons,
            'nearest_support': nearest_support,
            'nearest_resistance': nearest_resistance,
            'nearest_fib': nearest_fib,
            'volume_ratio': round(vol_ratio, 2),
            'pattern': pattern
        }
    
    def print_analysis(self, analysis):
        print(f"\n{'='*60}")
        print(f"SMC ANALYST - {self.symbol}")
        print(f"{'='*60}")
        print(f"[PRECIO ACTUAL] Precio actual de mercado: {analysis['entry_price']} USDT")
        print(f"Senal: {analysis['signal']} (confianza {analysis['confidence']}%)")
        if analysis['signal'] != 'NEUTRAL':
            print(f"Operacion: {'LONG' if analysis['signal']=='BUY' else 'SHORT'}")
            print(f"Precio de entrada: {analysis['entry_price']}")
            print(f"[TP] Take Profit: {analysis['tp_price']} (+{analysis['tp_percent']}%)")
            print(f"[SL] Stop Loss: {analysis['sl_price']} (-{analysis['sl_percent']}%)")
            print(f"Capital: ${analysis['capital_usd']} | Apalancamiento: {analysis['leverage']}x")
            print(f"Tamano posicion: ${analysis['position_size_usd']}")
            print(f"[GANANCIA] Ganancia si acierta: +${analysis['profit_if_win_usd']}")
            print(f"[PERDIDA] Perdida si falla: -${analysis['loss_if_loss_usd']}")
        else:
            print("No se detectaron condiciones claras de entrada.")
        print(f"\nRazones:")
        for r in analysis['reasons']:
            print(f"  - {r}")
        print(f"\nDatos tecnicos:")
        if analysis['nearest_support']:
            print(f"  Soporte mensual cercano: {analysis['nearest_support']:.2f}")
        if analysis['nearest_resistance']:
            print(f"  Resistencia mensual cercana: {analysis['nearest_resistance']:.2f}")
        if analysis['nearest_fib']:
            print(f"  Fibonacci cercano: {analysis['nearest_fib'][0]} = {analysis['nearest_fib'][1]:.2f}")
        print(f"  Volumen ratio vs media: {analysis['volume_ratio']}")
        print(f"  Patron de vela (4H): {analysis['pattern'] if analysis['pattern'] else 'Ninguno'}")
        print(f"{'='*60}\n")
    
    def run(self):
        analysis = self.analyze()
        self.print_analysis(analysis)
        from data.database import Database
        db = Database()
        db.save_signal(
            analyst_name=self.name,
            timeframe=f"{self.tf_analysis}_to_{self.tf_entry}",
            signal_type=analysis['signal'],
            entry_price=analysis['entry_price'],
            tp_price=analysis['tp_price'],
            sl_price=analysis['sl_price'],
            confidence=analysis['confidence'],
            symbol=self.symbol
        )
        db.close()
        
        notifier = TelegramNotifier()
        if analysis['signal'] != 'NEUTRAL':
            notifier.send_signal(
                analyst_name=self.name,
                symbol=self.symbol,
                signal_type=analysis['signal'],
                entry=analysis['entry_price'],
                tp=analysis['tp_price'],
                sl=analysis['sl_price'],
                confidence=analysis['confidence'],
                extra_info=f"Apalancamiento {analysis['leverage']}x | Riesgo {analysis['sl_percent']}%% | Beneficio {analysis['tp_percent']}%%"
            )
        else:
            notifier.send_message(f"SMC Analyst para {self.symbol}: Senal NEUTRAL. {', '.join(analysis['reasons'])}")
        
        return analysis