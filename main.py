# main.py
import sys
import io
# Forzar stdout y stderr a UTF-8 para evitar UnicodeEncodeError en Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

import argparse
import os
import atexit
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from data.binance_client import BinanceClient
from data.database import Database
from analysts.gem_hunter import GemHunter
from analysts.smc_analyst import SMCAnalyst
from analysts.sr_breakout_analyst import SRBreakoutAnalyst
from utils.report_generator import ReportGenerator
from utils.ticket_manager import TicketManager
from utils.futures_filters import FuturesFilters
from utils.auto_validator import AutoValidator
from config import SYMBOL, MODE, AUTO_VALIDATION

# Inicializar validador automático (solo si está habilitado)
validator = None
if AUTO_VALIDATION['enabled']:
    validator = AutoValidator()
    validator.start()
    atexit.register(lambda: validator.stop() if validator else None)

def generate_report():
    report_gen = ReportGenerator()
    detailed_report = report_gen.generate_detailed_report()
    print(detailed_report)
    print("\n✅ Reporte completo generado. Revisa los archivos performance*.png")

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

def run_gem_hunter():
    hunter = GemHunter()
    hunter.run()

def run_smc_analyst(symbol=SYMBOL):
    analyst = SMCAnalyst(symbol)
    analyst.run()

def run_sr_breakout_scan():
    analyst = SRBreakoutAnalyst()
    analyst.run()

def main():
    parser = argparse.ArgumentParser(description='Sistema de análisis de criptomonedas - Comandos disponibles')
    subparsers = parser.add_subparsers(dest='command', help='Comandos')

    subparsers.add_parser('sr-scan', help='Escanea 100 monedas buscando toques de soporte/resistencia (1M y 1W) en 4H. Prioriza bajo precio (excepto BTC/ETH) y excluye stablecoins.')
    subparsers.add_parser('gem-hunter', help='Busca criptomonedas infravaloradas (gemas ocultas) en top 100 pares USDT.')
    parser_smc = subparsers.add_parser('smc-analyze', help='Analisis SMC: S/R mensual + Fibonacci + Volumen + Patrones, con TP/SL fijos (3%%/1.5%%)')
    parser_smc.add_argument('--symbol', default=SYMBOL, help='Simbolo a analizar (ej. BTCUSDT)')
    subparsers.add_parser('generate-report', help='Generar reporte detallado de aciertos (con desglose por simbolo)')
    subparsers.add_parser('create-ticket', help='Crear ticket manual de acierto/fallo')
    parser_filters = subparsers.add_parser('show-filters', help='Mostrar funding rate, liquidaciones y order book')
    parser_filters.add_argument('--symbol', default=SYMBOL, help='Simbolo a consultar')

    args = parser.parse_args()

    if args.command == 'sr-scan':
        run_sr_breakout_scan()
    elif args.command == 'gem-hunter':
        run_gem_hunter()
    elif args.command == 'smc-analyze':
        run_smc_analyst(args.symbol)
    elif args.command == 'generate-report':
        generate_report()
    elif args.command == 'create-ticket':
        create_ticket_interactive()
    elif args.command == 'show-filters':
        show_futures_filters(args.symbol)
    else:
        parser.print_help()

if __name__ == '__main__':
    main()