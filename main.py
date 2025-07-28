# Proyecto: Memecoin Tracker + Alerta de Retiro Inteligente
# Tecnologías: Python + DexScreener + CoinGecko + Telegram Bot + Render Deploy

import requests
import time
import logging
from datetime import datetime
from telegram import Bot

# Cargar las keys
TELEGRAM_API_KEY = 8351984237:AAF0O8zv0lxtQR-aBYx2-iuGqXfE_T7SdWY
TELEGRAM_CHAT_ID = 7941357326

bot = Bot(token=TELEGRAM_API_KEY)

# Historial para evitar spam
alerted_tokens = {}
history = []

# Parámetros para alertas
DROP_PERCENT_ALERT = 15
DROP_CAP_ALERT = 20
SELL_BUY_RATIO_ALERT = 1.5

# Función para enviar mensajes a Telegram
def send_alert(message):
    bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)

# Consulta DexScreener
def fetch_dexscreener_tokens():
    try:
        url = "https://api.dexscreener.com/latest/dex/pairs/ethereum"
        res = requests.get(url)
        data = res.json()
        return data.get("pairs", [])
    except Exception as e:
        logging.error(f"Error en DexScreener: {e}")
        return []

# Consulta CoinGecko
def fetch_coingecko_token_data(symbol):
    try:
        url = f"https://api.coingecko.com/api/v3/coins/{symbol}"
        res = requests.get(url)
        return res.json()
    except:
        return None

# Lógica de evaluación

def should_alert(pair):
    try:
        # Evita spam
        if pair['pairAddress'] in alerted_tokens:
            return False

        price_change = float(pair['priceChange']['m5'])
        cap_change = float(pair['priceChange']['h1'])
        buy_tx = pair['txCount']['m5']['buys']
        sell_tx = pair['txCount']['m5']['sells']
        ratio = sell_tx / (buy_tx + 1)

        if price_change <= -DROP_PERCENT_ALERT or cap_change <= -DROP_CAP_ALERT or ratio >= SELL_BUY_RATIO_ALERT:
            return True

        return False
    except Exception as e:
        logging.error(f"Error en should_alert: {e}")
        return False

# Mensaje formateado

def format_alert(pair):
    name = pair['baseToken']['name']
    symbol = pair['baseToken']['symbol']
    price = pair['priceUsd']
    link = f"https://dexscreener.com/ethereum/{pair['pairAddress']}"

    return f"\n🛑 ALERTA DE RETIRO – ${symbol}\n\n💸 Precio: ${price[:7]}\n📉 Movimiento negativo en últimas 2 velas\n🔄 Volumen de ventas alto\n🔗 {link}\n\n(No es consejo financiero)"

# Loop principal

def run_monitor():
    while True:
        print("⏳ Buscando tokens...")
        tokens = fetch_dexscreener_tokens()

        for pair in tokens[:50]:
            if should_alert(pair):
                msg = format_alert(pair)
                send_alert(msg)
                alerted_tokens[pair['pairAddress']] = True
                history.append({
                    "timestamp": datetime.now().isoformat(),
                    "token": pair['baseToken']['symbol'],
                    "reason": "alert"
                })
        
        time.sleep(300)  # Cada 5 minutos

if __name__ == "__main__":
    run_monitor()
