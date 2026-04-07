# main.py (completo con nuevo comando)
import argparse
import sys
import os
import time
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from data.binance_client import BinanceClient
from data.database import Database
from analysts.analyst_1h import Analyst1H
from analysts.analyst_4h import Analyst4H
from analysts.analyst_1d import Analyst1D
from analysts.analyst_1m import Analyst1M
from committee.leader import LeaderAnalyst
from utils.report_generator import ReportGenerator
from utils.ticket_manager import TicketManager
from utils.futures_filters import FuturesFilters
from utils.order_simulator import SignalMonitor
from config import SYMBOL, MODE, SYMBOLS

# Variable global para el monitor de señales (si se usa)
signal_monitor = None

def run_individual_analyst(timeframe, symbol=SYMBOL):
    client = BinanceClient()
    db = Database()
    if timeframe == '1h':
        analyst = Analyst1H()
    elif timeframe == '4h':
        analyst = Analyst4H()
    elif timeframe == '1d':
        analyst = Analyst1D()
    elif timeframe == '1M':
        analyst = Analyst1M()
    else:
        print(f"Timeframe no válido: {timeframe}")
        return
    df = client.get_klines(symbol, analyst.timeframe, limit=300)
    if df.empty:
        print(f"No se pudieron obtener datos para {symbol}.")
        return
    analyst.load_data(df)
    signal = analyst.generate_signal()
    print(f"=== {analyst.name} ({analyst.timeframe}) - {symbol} ===")
    print(f"Señal: {signal['signal']}")
    print(f"Confianza: {signal['confidence']}%")
    print(f"Entrada sugerida: {signal['entry_price']}")
    print(f"Take Profit: {signal['tp_price']}")
    print(f"Stop Loss: {signal['sl_price']}")
    print(f"Razones: {', '.join(signal.get('reasons', []))}")
    if 'fibonacci_levels' in signal:
        print(f"Fibonacci: {signal['fibonacci_levels']}")
    if 'patterns' in signal:
        print(f"Patrones detectados: {signal['patterns']}")
    db.save_signal(analyst.name, analyst.timeframe, signal['signal'], 
                   signal['entry_price'], signal['tp_price'], signal['sl_price'], signal['confidence'], symbol)
    db.close()

def run_all_analysts_and_leader(symbol=SYMBOL, auto_simulate=False):
    global signal_monitor
    client = BinanceClient()
    analysts = [Analyst1H(), Analyst4H(), Analyst1D(), Analyst1M()]
    leader = LeaderAnalyst(symbol=symbol)
    
    # Si se activa la simulación, iniciar monitor
    if auto_simulate and signal_monitor is None:
        signal_monitor = SignalMonitor()
    
    signals = {}
    for analyst in analysts:
        df = client.get_klines(symbol, analyst.timeframe, limit=300)
        if df.empty:
            print(f"⚠️ Error con {analyst.name} para {symbol}")
            continue
        analyst.load_data(df)
        sig = analyst.generate_signal()
        signals[analyst.name] = sig
        print(f"\n{analyst.name} ({analyst.timeframe}): {sig['signal']} (confianza {sig['confidence']}%)")
        print(f"  TP: {sig['tp_price']} | SL: {sig['sl_price']}")
    
    final = leader.consolidate_signals(signals, apply_filters=True, auto_simulate=auto_simulate, signal_monitor=signal_monitor)
    
    print(f"\n=== ANÁLISIS DEL COMITÉ (LÍDER) para {symbol} ===")
    print(f"Señal final: {final['signal']} (confianza {final['confidence']}%)")
    print(f"Precio de entrada: {final['entry_price']}")
    print(f"Take Profit: {final['tp_price']}")
    print(f"Stop Loss: {final['sl_price']}")
    print(f"Entradas escalonadas: {final['staggered_entry']}")
    print(f"TPs escalonados: {final['staggered_tp']}")
    print(f"Riesgo por operación: {final['risk_percent']}% del capital")
    print(f"Tamaño de posición sugerido: {final['position_size_percent']}% del capital")
    print(f"Ratio Riesgo/Recompensa: {final['risk_reward_ratio']}")
    if final.get('filters_messages'):
        print("Filtros:", final['filters_messages'])
    
    if MODE == 'semi_auto' and final['signal'] != 'NEUTRAL' and not auto_simulate:
        resp = input(f"\n¿Ejecutar orden {final['signal']} para {symbol}? (s/n): ")
        if resp.lower() == 's':
            print("Simulando ejecución de orden...")
            print(f"Orden {final['signal']} enviada: entrada {final['entry_price']}, SL {final['sl_price']}, TP {final['tp_price']}")
        else:
            print("Orden cancelada por el usuario.")
    
    return final

def run_multi_symbols(symbols=None, auto_simulate=False):
    if symbols is None:
        symbols = SYMBOLS
    for sym in symbols:
        print(f"\n{'='*50}\nAnalizando {sym}\n{'='*50}")
        run_all_analysts_and_leader(symbol=sym, auto_simulate=auto_simulate)
        if auto_simulate:
            print(f"Simulación activa para {sym}. Las órdenes se monitorearán hasta TP/SL.")

def generate_report(symbol=None):
    report_gen = ReportGenerator()
    if symbol:
        print(report_gen.generate_text_report(symbol=symbol))
        report_gen.generate_performance_chart(save_path=f'performance_{symbol}.png', symbol=symbol)
    else:
        report_gen.generate_full_report()

def create_ticket_interactive():
    tm = TicketManager()
    tm.interactive_ticket()

def show_futures_filters(symbol=SYMBOL):
    filters = FuturesFilters(symbol)
    fr = filters.client.get_funding_rate(symbol)
    fr_ok, fr_msg = filters.funding_rate_filter('BUY')
    liq_ok, liq_msg = filters.liquidation_cascade_filter()
    imbalance = filters.order_book_imbalance()
    print(f"=== Filtros para {symbol} ===")
    print(f"Funding rate actual: {fr:.4%}")
    print(f"Liquidaciones: {liq_msg}")
    print(f"Order book imbalance (10 niveles): {imbalance:.3f} (positivo = presión compradora)")

def main():
    parser = argparse.ArgumentParser(description='Sistema de análisis de criptomonedas con comité de analistas')
    subparsers = parser.add_subparsers(dest='command', help='Comandos disponibles')
    
    parser_analyst = subparsers.add_parser('run-analyst', help='Ejecutar un analista individual')
    parser_analyst.add_argument('--timeframe', required=True, choices=['1h', '4h', '1d', '1M'])
    parser_analyst.add_argument('--symbol', default=SYMBOL, help='Símbolo a analizar (ej. BTCUSDT)')
    
    parser_all = subparsers.add_parser('run-all', help='Ejecutar todos los analistas y el líder para un símbolo')
    parser_all.add_argument('--symbol', default=SYMBOL, help='Símbolo a analizar')
    
    parser_multi = subparsers.add_parser('run-all-multi', help='Ejecutar comité para múltiples símbolos')
    parser_multi.add_argument('--symbols', nargs='+', default=SYMBOLS, help='Lista de símbolos')
    
    # Nuevo comando con simulador automático
    parser_sim = subparsers.add_parser('run-with-simulator', help='Ejecuta el comité y simula órdenes automáticas (monitorea TP/SL)')
    parser_sim.add_argument('--symbol', default=SYMBOL, help='Símbolo a analizar')
    parser_sim.add_argument('--symbols', nargs='+', help='Opcional: múltiples símbolos')
    
    parser_report = subparsers.add_parser('generate-report', help='Generar reporte de aciertos y gráfico')
    parser_report.add_argument('--symbol', default=None, help='Filtrar por símbolo (opcional)')
    
    subparsers.add_parser('create-ticket', help='Crear ticket de acierto/fallo (interactivo)')
    
    parser_filters = subparsers.add_parser('show-filters', help='Mostrar funding rate, liquidaciones y order book')
    parser_filters.add_argument('--symbol', default=SYMBOL, help='Símbolo a consultar')
    
    args = parser.parse_args()
    
    if args.command == 'run-analyst':
        run_individual_analyst(args.timeframe, args.symbol)
    elif args.command == 'run-all':
        run_all_analysts_and_leader(args.symbol, auto_simulate=False)
    elif args.command == 'run-all-multi':
        run_multi_symbols(args.symbols, auto_simulate=False)
    elif args.command == 'run-with-simulator':
        if args.symbols:
            run_multi_symbols(args.symbols, auto_simulate=True)
        else:
            run_all_analysts_and_leader(args.symbol, auto_simulate=True)
        # Mantener el programa corriendo para que el monitor WebSocket siga activo
        print("\nSimulador activo. Las órdenes se monitorearán. Presiona Ctrl+C para detener.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nDeteniendo simulador...")
            if signal_monitor:
                signal_monitor.stop_all()
    elif args.command == 'generate-report':
        generate_report(args.symbol)
    elif args.command == 'create-ticket':
        create_ticket_interactive()
    elif args.command == 'show-filters':
        show_futures_filters(args.symbol)
    else:
        parser.print_help()

if __name__ == '__main__':
    main()