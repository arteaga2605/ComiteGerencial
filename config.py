# config.py
SYMBOL = 'BTCUSDT'  # símbolo por defecto (compatibilidad)
SYMBOLS = ['BTCUSDT', 'LINKUSDT', 'SOLUSDT']  # lista para análisis múltiple
DB_PATH = 'trading_signals.db'

# Timeframes
TIMEFRAMES = {
    '1h': '1h',
    '4h': '4h',
    '1d': '1d',
    '1M': '1M'
}

# Risk management
RISK_PERCENT = 0.02  # 2% del capital por operación
MIN_RISK_REWARD_RATIO = 2.0  # mínimo 1:2

# Futures settings (Binance Futures)
FUTURES_FUNDING_RATE_THRESHOLD = 0.005  # 0.5% funding rate como límite
FUTURES_LEVERAGE_MAX = 10  # apalancamiento máximo sugerido

# Modo de operación: 'analysis' o 'semi_auto'
MODE = 'analysis'  # 'analysis' solo muestra señales, 'semi_auto' pide confirmación