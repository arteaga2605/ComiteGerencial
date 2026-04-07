# committee/leader.py (fragmento modificado, pero doy el archivo completo)
import pandas as pd
import numpy as np
from data.database import Database
from config import RISK_PERCENT, MIN_RISK_REWARD_RATIO, MODE
from utils.ml_weights import MLWeightAdjuster
from utils.futures_filters import FuturesFilters

class LeaderAnalyst:
    def __init__(self, symbol='BTCUSDT'):
        self.name = 'Leader_Committee'
        self.db = Database()
        self.ml_adjuster = MLWeightAdjuster()
        self.symbol = symbol
        self.filters = FuturesFilters(symbol)
    
    def consolidate_signals(self, signals_dict, apply_filters=True, auto_simulate=False, signal_monitor=None):
        base_weights = {
            'Analyst_1H': 0.1,
            'Analyst_4H': 0.2,
            'Analyst_1D': 0.3,
            'Analyst_1M': 0.4
        }
        adjusted_weights = self.ml_adjuster.get_adjusted_weights(base_weights)
        
        buy_score = 0
        sell_score = 0
        total_weight = 0
        entry_prices = []
        tp_prices = []
        sl_prices = []
        confidences = []
        
        for name, sig in signals_dict.items():
            if sig['signal'] == 'BUY':
                buy_score += adjusted_weights[name] * (sig['confidence'] / 100)
            elif sig['signal'] == 'SELL':
                sell_score += adjusted_weights[name] * (sig['confidence'] / 100)
            
            entry_prices.append(sig['entry_price'])
            tp_prices.append(sig['tp_price'])
            sl_prices.append(sig['sl_price'])
            confidences.append(sig['confidence'])
            total_weight += adjusted_weights[name]
        
        if buy_score > sell_score and buy_score > 0.2:
            final_signal = 'BUY'
            confidence = int((buy_score / total_weight) * 100)
        elif sell_score > buy_score and sell_score > 0.2:
            final_signal = 'SELL'
            confidence = int((sell_score / total_weight) * 100)
        else:
            final_signal = 'NEUTRAL'
            confidence = 0
        
        filters_passed = True
        filter_messages = []
        if apply_filters and final_signal != 'NEUTRAL':
            fr_ok, fr_msg = self.filters.funding_rate_filter(final_signal)
            liq_ok, liq_msg = self.filters.liquidation_cascade_filter()
            if not fr_ok:
                filters_passed = False
                filter_messages.append(fr_msg)
            if not liq_ok:
                filters_passed = False
                filter_messages.append(liq_msg)
        
        if not filters_passed:
            final_signal = 'NEUTRAL'
            confidence = 0
            print("Filtros bloquean la señal:", filter_messages)
        
        if final_signal != 'NEUTRAL':
            compatible_entries = [signals_dict[name]['entry_price'] for name in signals_dict if signals_dict[name]['signal'] == final_signal]
            entry = np.mean(compatible_entries) if compatible_entries else np.mean(entry_prices)
            compatible_tp = [signals_dict[name]['tp_price'] for name in signals_dict if signals_dict[name]['signal'] == final_signal]
            compatible_sl = [signals_dict[name]['sl_price'] for name in signals_dict if signals_dict[name]['signal'] == final_signal]
            tp = np.mean(compatible_tp) if compatible_tp else np.mean(tp_prices)
            sl = np.mean(compatible_sl) if compatible_sl else np.mean(sl_prices)
        else:
            entry = np.mean(entry_prices)
            tp = np.mean(tp_prices)
            sl = np.mean(sl_prices)
        
        staggered = self.calculate_staggered_levels(entry, tp, sl, final_signal)
        
        risk_amount = entry - sl if final_signal == 'BUY' else sl - entry
        if risk_amount <= 0:
            position_size_percent = RISK_PERCENT
        else:
            position_size_percent = RISK_PERCENT * (entry / risk_amount)
            position_size_percent = min(position_size_percent, 0.1)
        
        rr_ratio = (tp - entry) / (entry - sl) if final_signal == 'BUY' and (entry - sl) > 0 else (entry - tp) / (sl - entry) if final_signal == 'SELL' and (sl - entry) > 0 else 0
        
        analysis = {
            'signal': final_signal,
            'confidence': confidence,
            'entry_price': round(entry, 2),
            'tp_price': round(tp, 2),
            'sl_price': round(sl, 2),
            'staggered_entry': staggered['entries'],
            'staggered_tp': staggered['tps'],
            'risk_percent': RISK_PERCENT * 100,
            'position_size_percent': round(position_size_percent * 100, 2),
            'risk_reward_ratio': round(rr_ratio, 2),
            'filters_messages': filter_messages,
            'individual_signals': signals_dict
        }
        
        self.db.save_signal(self.name, 'multi', final_signal, analysis['entry_price'], analysis['tp_price'], analysis['sl_price'], confidence, self.symbol)
        
        # Simulación automática si se solicita
        if auto_simulate and signal_monitor and final_signal != 'NEUTRAL':
            signal_monitor.add_signal(self.symbol, self.name, final_signal, entry, tp, sl, confidence)
        
        return analysis
    
    def calculate_staggered_levels(self, entry, tp, sl, signal_type, num_entries=3, num_tps=3):
        if signal_type == 'NEUTRAL':
            return {'entries': [], 'tps': []}
        if signal_type == 'BUY':
            step_entry = (entry - sl) / num_entries
            entries = [entry - i * step_entry for i in range(num_entries)]
            step_tp = (tp - entry) / num_tps
            tps = [entry + (i+1) * step_tp for i in range(num_tps)]
        else:  # SELL
            step_entry = (sl - entry) / num_entries
            entries = [entry + i * step_entry for i in range(num_entries)]
            step_tp = (entry - tp) / num_tps
            tps = [entry - (i+1) * step_tp for i in range(num_tps)]
        return {'entries': [round(e,2) for e in entries], 'tps': [round(t,2) for t in tps]}
    
    def run_committee(self, analysts_list, binance_client, symbol, auto_simulate=False, signal_monitor=None):
        signals = {}
        for analyst in analysts_list:
            df = binance_client.get_klines(symbol, analyst.timeframe, limit=300)
            if df.empty:
                print(f"⚠️ Error obteniendo datos para {analyst.name} con símbolo {symbol}")
                continue
            analyst.load_data(df)
            signal = analyst.generate_signal()
            signals[analyst.name] = signal
            self.db.save_signal(analyst.name, analyst.timeframe, signal['signal'], 
                                signal['entry_price'], signal['tp_price'], signal['sl_price'], signal['confidence'], symbol)
            # También se podría simular individualmente, pero por ahora solo el líder
        return self.consolidate_signals(signals, auto_simulate=auto_simulate, signal_monitor=signal_monitor)