# config.py
# Configuración principal del sistema

SYMBOL = 'BTCUSDT'
SYMBOLS = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT']
DB_PATH = 'trading_signals.db'

TIMEFRAMES = {
    '1h': '1h',
    '4h': '4h',
    '1d': '1d',
    '1M': '1M'
}

RISK_PERCENT = 0.02
MIN_RISK_REWARD_RATIO = 2.0

FUTURES_FUNDING_RATE_THRESHOLD = 0.005
FUTURES_LEVERAGE_MAX = 10

MODE = 'analysis'

AUTO_VALIDATION = {
    'enabled': False,
    'check_interval_seconds': 60,
    'max_wait_hours': 48,
    'default_sl_percent': 2.0,
    'default_tp_percent': 4.0
}

GEM_HUNTER = {
    'max_pairs': 100,
    'min_volume_usdt_24h': 1_000_000,
    'min_score': 60,
    'max_results': 3,
    'timeframes_to_consider': ['1h', '4h', '1d']
}

SMC_STRATEGY = {
    'capital_usd': 10.0,
    'leverage': 10,
    'tp_percent': 3.0,
    'sl_percent': 1.5,
    'timeframe_entry': '4h',
    'timeframe_analysis': '1M'
}

# SR Breakout Analyst - Escanea 100 monedas
SR_SCAN_CONFIG = {
    'max_pairs': 100,                    # Volvemos a 100
    'timeframe_entry': '4h',
    'tolerance_percent': 1.5,
    'min_volume_usdt_24h': 500_000,
    'low_price_threshold': 10.0,
    'exclude_stablecoins': True,
    'min_score': 50,
    'max_results': 20,                   # Mostrar hasta 20 resultados
    'always_include_btc': True,
    'blacklist_base_keywords': [
        'USD', 'USDC', 'BUSD', 'DAI', 'TUSD', 'USDP', 'FDUSD', 'USDD', 'LUSD', 'GUSD', 'HUSD',
        'USD1', 'XUSD', 'USDE', 'EUR', 'GBP', 'JPY', 'CNY', 'KRW', 'RUB', 'TRY', 'BRL',
        'PAX', 'TUSD', 'USDS', 'USDX', 'USD+'
    ]
}

# Telegram
TELEGRAM_BOT_TOKEN = "7572284138:AAGWLPM5iIeXqi_sx2VgBkWie_LPTXy2xt0"
TELEGRAM_CHAT_ID = "-4642309937"
TELEGRAM_ENABLED = True