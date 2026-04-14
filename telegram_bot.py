# telegram_bot.py
import subprocess
import sys
import os
import asyncio
import tempfile
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from telegram.error import NetworkError, TimedOut
from config import TELEGRAM_BOT_TOKEN

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

COMMANDS = {
    "sr_scan": {
        "name": "Analista S/R Mensual",
        "cmd": ["python", "main.py", "sr-scan"],
        "description": "Escanea 100 monedas buscando soportes/resistencias"
    },
    "gem_hunter": {
        "name": "Cazador de Gemas",
        "cmd": ["python", "main.py", "gem-hunter"],
        "description": "Busca criptos infravaloradas (100 monedas)"
    },
    "smc_analyze": {
        "name": "Analista SMC",
        "cmd": ["python", "main.py", "smc-analyze", "--symbol", "BTCUSDT"],
        "description": "Análisis Smart Money Concepts (BTC)"
    },
    "report": {
        "name": "Generar Reporte",
        "cmd": ["python", "main.py", "generate-report"],
        "description": "Genera gráfico de rendimiento"
    },
    "ticket": {
        "name": "Crear Ticket Manual",
        "cmd": ["python", "main.py", "create-ticket"],
        "description": "Registrar operación manualmente"
    }
}

async def send_menu(chat_id, context, message_id=None):
    keyboard = []
    for key, cmd_info in COMMANDS.items():
        keyboard.append([InlineKeyboardButton(cmd_info["name"], callback_data=key)])
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = (
        "🤖 *Sistema de Trading Crypto*\n\n"
        "Selecciona una opción para ejecutar el análisis:\n"
        "Los resultados se enviarán automáticamente a este chat.\n\n"
        "⚠️ El escaneo de 100 monedas puede tardar hasta 3-4 minutos."
    )
    for attempt in range(3):
        try:
            if message_id:
                await context.bot.edit_message_text(
                    text=text,
                    chat_id=chat_id,
                    message_id=message_id,
                    reply_markup=reply_markup,
                    parse_mode="Markdown"
                )
            else:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    reply_markup=reply_markup,
                    parse_mode="Markdown"
                )
            return
        except (NetworkError, TimedOut):
            await asyncio.sleep(2)
        except Exception:
            break

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        await send_menu(chat_id, context, query.message.message_id)
    else:
        await send_menu(chat_id, context)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    command_key = query.data
    cmd_info = COMMANDS.get(command_key)
    if not cmd_info:
        await query.edit_message_text("Comando no reconocido.")
        return

    await query.edit_message_text(f"🔄 Ejecutando: {cmd_info['name']}...\nEsto puede tomar varios minutos (hasta 5). Por favor espera.")

    try:
        # Timeout de 600 segundos = 10 minutos
        result = subprocess.run(
            cmd_info["cmd"],
            capture_output=True,
            text=True,
            timeout=600,
            encoding='utf-8',
            errors='replace'
        )
        output = result.stdout + result.stderr
        if len(output) > 3500:
            # Enviar como archivo
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
                f.write(output)
                tmp_path = f.name
            with open(tmp_path, 'rb') as f:
                await context.bot.send_document(
                    chat_id=update.effective_chat.id,
                    document=f,
                    filename=f"resultado_{cmd_info['name'].replace(' ', '_')}.txt",
                    caption=f"✅ Resultado de {cmd_info['name']} (archivo adjunto)"
                )
            os.unlink(tmp_path)
        else:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"✅ *Resultado de {cmd_info['name']}:*\n```\n{output}\n```",
                parse_mode="Markdown"
            )
    except subprocess.TimeoutExpired:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="⏰ El comando tardó más de 10 minutos. Puedes reducir 'max_pairs' en config.py o intentar más tarde."
        )
    except Exception as e:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"❌ Error: {str(e)}"
        )

    await send_menu(update.effective_chat.id, context)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Usa /start para ver el menú de botones.")

def main():
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).connect_timeout(30).read_timeout(30).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CallbackQueryHandler(button_callback))
    print("🤖 Bot de Telegram iniciado...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()