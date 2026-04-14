# analysts/sr_breakout_analyst.py
import pandas as pd
import numpy as np
import time
import requests
from data.binance_client import BinanceClient
from config import SR_SCAN_CONFIG
from utils.telegram_notifier import TelegramNotifier

class SRBreakoutAnalyst:
    def __init__(self):
        self.name = "SR_Breakout_Analyst"
        self.client = BinanceClient()
        self.max_pairs = SR_SCAN_CONFIG['max_pairs']
        self.timeframe_entry = SR_SCAN_CONFIG['timeframe_entry']
        self.tolerance_percent = SR_SCAN_CONFIG['tolerance_percent'] / 100
        self.min_volume_usdt = SR_SCAN_CONFIG['min_volume_usdt_24h']
        self.low_price_threshold = SR_SCAN_CONFIG['low_price_threshold']
        self.exclude_stablecoins = SR_SCAN_CONFIG['exclude_stablecoins']
        self.min_score = SR_SCAN_CONFIG['min_score']
        self.max_results = SR_SCAN_CONFIG['max_results']
        self.always_include_btc = SR_SCAN_CONFIG['always_include_btc']
        self.blacklist_keywords = [kw.upper() for kw in SR_SCAN_CONFIG.get('blacklist_base_keywords', [])]
        self.results = []
    
    def is_stablecoin_base(self, base):
        if not self.exclude_stablecoins:
            return False
        base_upper = base.upper()
        for kw in self.blacklist_keywords:
            if kw in base_upper:
                return True
        return False
    
    def get_all_usdt_pairs(self):
        try:
            endpoint = f"{self.client.BASE_URL}/ticker/24hr"
            resp = requests.get(endpoint, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            
            usdt_pairs = []
            for item in data:
                symbol = item['symbol']
                if not symbol.endswith('USDT') or not symbol.isalnum():
                    continue
                base = symbol.replace('USDT', '')
                if self.is_stablecoin_base(base):
                    continue
                usdt_pairs.append(item)
            
            usdt_pairs.sort(key=lambda x: float(x['quoteVolume']), reverse=True)
            top_pairs = usdt_pairs[:self.max_pairs]
            
            symbols = []
            volumes = {}
            btc_found = False
            
            for pair in top_pairs:
                sym = pair['symbol']
                price = float(pair['lastPrice'])
                base = sym.replace('USDT', '')
                
                if self.always_include_btc and sym == 'BTCUSDT':
                    symbols.append(sym)
                    volumes[sym] = float(pair['quoteVolume'])
                    btc_found = True
                    continue
                
                if base in ['BTC', 'ETH'] or price <= self.low_price_threshold:
                    symbols.append(sym)
                    volumes[sym] = float(pair['quoteVolume'])
            
            if self.always_include_btc and not btc_found:
                for item in data:
                    if item['symbol'] == 'BTCUSDT':
                        symbols.insert(0, 'BTCUSDT')
                        volumes['BTCUSDT'] = float(item['quoteVolume'])
                        break
            
            return symbols, volumes
        except Exception as e:
            print(f"Error obteniendo pares: {e}")
            return [], {}
    
    def get_support_resistance_levels(self, symbol, timeframe):
        try:
            df = self.client.get_klines(symbol, timeframe, limit=100)
            if df.empty or len(df) < 20:
                return [], []
        except Exception:
            return [], []
        
        df['max_local'] = df['high'].rolling(window=5, center=True).max()
        df['min_local'] = df['low'].rolling(window=5, center=True).min()
        resistances = df[df['high'] == df['max_local']]['high'].dropna().unique()[-10:]
        supports = df[df['low'] == df['min_local']]['low'].dropna().unique()[-10:]
        return supports, resistances
    
    def check_price_near_level(self, current_price, levels):
        best_level = None
        best_diff = float('inf')
        for level in levels:
            diff = abs(current_price - level) / level * 100
            if diff < best_diff:
                best_diff = diff
                best_level = level
        if best_level is not None and best_diff <= self.tolerance_percent:
            return True, best_level, best_diff
        return False, None, None
    
    def calculate_score(self, symbol, current_price, volume_usdt, alerts):
        score = 0
        base = symbol.replace('USDT', '')
        
        if symbol == 'BTCUSDT':
            score += 40
        
        if base not in ['BTC', 'ETH']:
            if current_price < 1:
                score += 30
            elif current_price < 5:
                score += 20
            elif current_price < 10:
                score += 10
        
        if volume_usdt > 10_000_000:
            score += 25
        elif volume_usdt > 5_000_000:
            score += 15
        elif volume_usdt > 2_000_000:
            score += 10
        
        if alerts:
            min_dist = min(a['distance_percent'] for a in alerts)
            score += max(0, 30 - min_dist * 2)
        
        for a in alerts:
            if a['signal'] == 'BUY':
                score += 15
            elif a['signal'] == 'SELL':
                score += 10
        
        return min(100, score)
    
    def analyze_single_pair(self, symbol, volume):
        try:
            df_4h = self.client.get_klines(symbol, self.timeframe_entry, limit=1)
            if df_4h.empty:
                return None
            current_price = df_4h['close'].iloc[-1]
        except Exception:
            return None
        
        supports_1m, resistances_1m = self.get_support_resistance_levels(symbol, '1M')
        supports_1w, resistances_1w = self.get_support_resistance_levels(symbol, '1w')
        
        alerts = []
        
        near, level, dist = self.check_price_near_level(current_price, supports_1m)
        if near:
            alerts.append({'timeframe': '1M', 'type': 'SUPPORT', 'level': level, 'distance_percent': round(dist, 2), 'signal': 'BUY'})
        
        near, level, dist = self.check_price_near_level(current_price, resistances_1m)
        if near:
            alerts.append({'timeframe': '1M', 'type': 'RESISTANCE', 'level': level, 'distance_percent': round(dist, 2), 'signal': 'SELL'})
        
        near, level, dist = self.check_price_near_level(current_price, supports_1w)
        if near:
            alerts.append({'timeframe': '1W', 'type': 'SUPPORT', 'level': level, 'distance_percent': round(dist, 2), 'signal': 'BUY'})
        
        near, level, dist = self.check_price_near_level(current_price, resistances_1w)
        if near:
            alerts.append({'timeframe': '1W', 'type': 'RESISTANCE', 'level': level, 'distance_percent': round(dist, 2), 'signal': 'SELL'})
        
        if not alerts:
            return None
        
        score = self.calculate_score(symbol, current_price, volume, alerts)
        if score < self.min_score and symbol != 'BTCUSDT':
            return None
        
        return {
            'symbol': symbol,
            'current_price': round(current_price, 8),
            'volume_usdt': round(volume, 0),
            'score': score,
            'alerts': alerts
        }
    
    def scan_all_pairs(self):
        print("[BUSQUEDA] Escaneando gemas de bajo precio (max {} pares USDT)...".format(self.max_pairs))
        print("   Precio maximo para baja capitalizacion: <${} (excepto BTC/ETH)".format(self.low_price_threshold))
        print("   Excluyendo stablecoins (USD1, XUSD, USDE, etc.)")
        print("   Incluyendo BTC siempre: {}".format('SI' if self.always_include_btc else 'NO'))
        print("   Tolerancia S/R: {}% | Timeframe entrada: {}".format(self.tolerance_percent*100, self.timeframe_entry))
        print("   Volumen minimo: ${:,.0f} | Puntuacion minima: {}".format(self.min_volume_usdt, self.min_score))
        print()
        
        symbols, volumes = self.get_all_usdt_pairs()
        if not symbols:
            print("[ERROR] No se encontraron pares que cumplan los filtros.")
            return []
        
        results = []
        total = len(symbols)
        
        for i, sym in enumerate(symbols):
            vol = volumes.get(sym, 0)
            if vol < self.min_volume_usdt and sym != 'BTCUSDT':
                continue
            
            # Print sin caracteres especiales ni formato de moneda con coma
            msg = "Analizando {} ({}/{}) - Vol: {}".format(sym, i+1, total, int(vol))
            print(msg, end='\r')
            
            try:
                analysis = self.analyze_single_pair(sym, vol)
                if analysis:
                    results.append(analysis)
            except Exception:
                pass
            
            time.sleep(0.05)
        
        results.sort(key=lambda x: x['score'], reverse=True)
        results = results[:self.max_results]
        
        print("\n[OK] Escaneo completado.")
        return results
    
    def print_results(self, results):
        if not results:
            print("\n[INFO] No se encontraron oportunidades con puntuacion suficiente.")
            return
        
        print("\n" + "="*100)
        print("[TOP] TOP OPORTUNIDADES DE BAJO PRECIO (max {})".format(len(results)))
        print("="*100)
        
        for idx, res in enumerate(results, 1):
            btc_marker = " [BTC - INFLUYE EN TODO EL MERCADO]" if res['symbol'] == 'BTCUSDT' else ""
            print("\n{}. {}{} | Score: {} | Precio: {} USDT".format(idx, res['symbol'], btc_marker, res['score'], res['current_price']))
            print("   Volumen 24h: ${:,.0f}".format(res['volume_usdt']))
            for alert in res['alerts']:
                emoji_text = "[BUY]" if alert['signal'] == 'BUY' else "[SELL]"
                print("   {} {} {} en {:.8f} (distancia {}%) -> {}".format(emoji_text, alert['timeframe'], alert['type'], alert['level'], alert['distance_percent'], alert['signal']))
            
            if res['symbol'] == 'BTCUSDT':
                print("   [ATENCION] BTC es el lider del mercado. Su movimiento puede arrastrar a todas las altcoins.")
                if alert['signal'] == 'BUY':
                    print("   [TIP] Si BTC rebota en soporte, es probable que las altcoins tambien suban.")
                elif alert['signal'] == 'SELL':
                    print("   [TIP] Si BTC encuentra resistencia, es probable que el mercado corrija a la baja.")
        
        print("\n" + "="*100)
        print("[TIP] Recomendacion: Para bajo capital (10$ con 10x), prioriza senales BUY en soportes semanales/mensuales.")
        print("   Si BTC da senal, ajusta tus operaciones en altcoins en la misma direccion.")
        print("="*100)
    
    def save_results_to_db(self, results):
        from data.database import Database
        db = Database()
        for res in results:
            for alert in res['alerts']:
                signal_type = 'BUY' if alert['signal'] == 'BUY' else 'SELL'
                db.save_signal(
                    analyst_name=f"{self.name}_{alert['timeframe']}_{alert['type']}",
                    timeframe=self.timeframe_entry,
                    signal_type=signal_type,
                    entry_price=res['current_price'],
                    tp_price=0,
                    sl_price=0,
                    confidence=res['score'],
                    symbol=res['symbol']
                )
        db.close()
    
    def run(self):
        results = self.scan_all_pairs()
        self.print_results(results)
        self.save_results_to_db(results)
        
        notifier = TelegramNotifier()
        if results:
            for res in results:
                for alert in res['alerts']:
                    notifier.send_signal(
                        analyst_name=self.name,
                        symbol=res['symbol'],
                        signal_type=alert['signal'],
                        entry=res['current_price'],
                        tp=0,
                        sl=0,
                        confidence=res['score'],
                        extra_info=f"{alert['timeframe']} {alert['type']} a {alert['level']:.8f} (dist {alert['distance_percent']}%)"
                    )
        else:
            notifier.send_message("Escaneo S/R completado: No se encontraron oportunidades.")
        
        with open('sr_lowcap_opportunities.txt', 'w', encoding='utf-8') as f:
            f.write(f"Escaneo de bajo capital: {pd.Timestamp.now()}\n")
            f.write("="*100 + "\n")
            for res in results:
                f.write(f"\n{res['symbol']} | Score: {res['score']} | Precio: {res['current_price']} | Vol: ${res['volume_usdt']:,.0f}\n")
                for alert in res['alerts']:
                    f.write(f"  {alert['timeframe']} {alert['type']} en {alert['level']} (dist {alert['distance_percent']}%) -> {alert['signal']}\n")
        
        print("\n[FILE] Resultados guardados en 'sr_lowcap_opportunities.txt'")
        return results