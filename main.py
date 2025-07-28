import requests
import time
from datetime import datetime
import os

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        requests.post(url, data=payload)
    except Exception as e:
        print("Error al enviar mensaje:", e)

def get_memecoins():
    url = "https://api.coingecko.com/api/v3/coins/markets"
    params = {
        "vs_currency": "usd",
        "order": "market_cap_asc",  # Prioriza monedas pequeñas
        "per_page": 50,
        "page": 1,
        "price_change_percentage": "1h,24h"
    }
    try:
        response = requests.get(url, params=params)
        return response.json()
    except Exception as e:
        print("Error al obtener datos:", e)
        return []

def should_buy(coin):
    price = coin["current_price"]
    change_1h = coin.get("price_change_percentage_1h_in_currency", 0) or 0
    change_24h = coin.get("price_change_percentage_24h_in_currency", 0) or 0
    volume = coin["total_volume"]

    # Estrategia pensada por IA
    if change_1h > 10 and change_24h > 30 and volume > 50000:
        return True
    return False

def should_sell(coin, memory):
    symbol = coin["symbol"]
    price = coin["current_price"]
    high = memory.get(symbol, {}).get("highest", price)

    # Guardar el precio más alto
    if price > high:
        memory[symbol] = {"highest": price}

    percent_drop = ((high - price) / high) * 100 if high > price else 0

    if percent_drop >= 25:
        return f"🚨 *Posible Dump Detectado:* {symbol.upper()} ha caído un {percent_drop:.2f}% desde su punto más alto (${high:.4f})"
    if price > high * 0.8:
        return f"🟢 *Ganancia Alta:* {symbol.upper()} está cerca del +80% de su mejor precio. Considera retirar ganancias."

    return None

def track_memecoins():
    memory = {}
    while True:
        coins = get_memecoins()
        for coin in coins:
            symbol = coin["symbol"]
            name = coin["name"]
            price = coin["current_price"]

            if should_buy(coin):
                message = (
                    f"🚀 *Oportunidad Detectada*\n"
                    f"*{name}* ({symbol.upper()})\n"
                    f"💰 Precio: ${price}\n"
                    f"📈 1h: {coin.get('price_change_percentage_1h_in_currency', 0):.2f}% | "
                    f"24h: {coin.get('price_change_percentage_24h_in_currency', 0):.2f}%\n"
                    f"#memecoin #cryptoalert"
                )
                send_telegram_message(message)

            sell_alert = should_sell(coin, memory)
            if sell_alert:
                send_telegram_message(sell_alert)

        print(f"[{datetime.now().strftime('%H:%M:%S')}] Check completo")
        time.sleep(300)  # cada 5 minutos

if __name__ == "__main__":
    send_telegram_message("🤖 Tracker de memecoins iniciado 24/7...")
    track_memecoins()
