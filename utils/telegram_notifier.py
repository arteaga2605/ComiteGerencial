# utils/telegram_notifier.py
import requests
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, TELEGRAM_ENABLED

class TelegramNotifier:
    def __init__(self):
        self.token = TELEGRAM_BOT_TOKEN
        self.chat_id = TELEGRAM_CHAT_ID
        self.enabled = TELEGRAM_ENABLED
        self.base_url = f"https://api.telegram.org/bot{self.token}"
    
    def send_message(self, text, parse_mode='HTML'):
        if not self.enabled:
            return
        try:
            url = f"{self.base_url}/sendMessage"
            payload = {
                'chat_id': self.chat_id,
                'text': text,
                'parse_mode': parse_mode
            }
            response = requests.post(url, json=payload, timeout=10)
            return response.json()
        except Exception as e:
            print(f"Error enviando mensaje a Telegram: {e}")
            return None
    
    def send_signal(self, analyst_name, symbol, signal_type, entry, tp, sl, confidence, extra_info=""):
        """Envía una señal formateada"""
        if signal_type == 'BUY':
            emoji = "🟢 LONG"
        elif signal_type == 'SELL':
            emoji = "🔴 SHORT"
        else:
            emoji = "⚪ NEUTRAL"
        
        text = f"<b>📊 {analyst_name}</b>\n"
        text += f"<b>{symbol}</b> | {emoji} | Confianza: {confidence}%\n"
        text += f"💰 Entrada: {entry}\n"
        text += f"🎯 TP: {tp}\n"
        text += f"🛑 SL: {sl}\n"
        if extra_info:
            text += f"ℹ️ {extra_info}\n"
        text += f"🕒 {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        self.send_message(text)