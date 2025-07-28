import requests
import time
import os
from datetime import datetime

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown"
    }
    try:
        requests.post(url, data=payload)
    except Exception as e:
        print("Error enviando mensaje:", e)

def get_memecoins():
    url = "https://api.coingecko.com/api/v3/coins/markets"
    params = {
        "vs_currency": "usd",
        "order": "market_cap_asc",
        "per_page": 50,
        "page": 1,
        "price_change_percentage": "1h,24h"
    }
    try:
        r = requests.get(url, params=params)
        return r.json()
    except Exception as e:
        print("Error obteniendo datos:", e)
        return []

def should_buy(coin):
    change_1h = coin.get("price_change_percentage_1h_in_currency") or 0
    change_24h = coin.get("price_change_percentage_24h_in_currency") or 0
    volume = coin.get("total_volume") or 0

    return change_1h > 10 and change_24h > 30 and volume > 50000

def should_sell(coin, memory):
    symbol = coin["symbol"]
    price = coin["current_price"]
    high = memory.get(symbol, {}).get("highest", price)

    if price > high:
        memory[symbol] = {"highest": price}

    percent_drop = ((high - price) / high) * 100 if high > price else 0

    if percent_drop >= 25:
        return f"🚨 *Posible Dump:* {symbol.upper()} cayó {percent_drop:.2f}% desde su pico (${high:.4f})"
    if price > high * 0.8:
        return f"🟢 *Ganancia Alta:* {symbol.upper()} cerca del +80% de su pico. Considera vender."

    return None

def track_memecoins():
    memory = {}
    alertas_enviadas = {}
    send_telegram_message("🤖 Bot Tracker de Memecoins iniciado 24/7...")

    while True:
        coins = get_memecoins()
        for coin in coins:
            symbol = coin["symbol"]

            if should_buy(coin):
                if not alertas_enviadas.get(f"buy_{symbol}", False):
                    coin_link = f"https://www.coingecko.com/en/coins/{coin['id']}"
                    msg = (
                        f"🚀 *Oportunidad Detectada*\n"
                        f"*{coin['name']}* ({symbol.upper()})\n"
                        f"Precio: ${coin['current_price']}\n"
                        f"1h: {coin.get('price_change_percentage_1h_in_currency', 0):.2f}% | "
                        f"24h: {coin.get('price_change_percentage_24h_in_currency', 0):.2f}%\n"
                        f"[Ver en CoinGecko]({coin_link})\n"
                        f"#memecoin #cryptoalert"
                    )
                    send_telegram_message(msg)
                    alertas_enviadas[f"buy_{symbol}"] = True
            else:
                alertas_enviadas[f"buy_{symbol}"] = False

            sell_alert = should_sell(coin, memory)
            if sell_alert:
                if alertas_enviadas.get(f"sell_{symbol}", "") != sell_alert:
                    send_telegram_message(sell_alert)
                    alertas_enviadas[f"sell_{symbol}"] = sell_alert
            else:
                alertas_enviadas[f"sell_{symbol}"] = False

        print(f"[{datetime.now().strftime('%H:%M:%S')}] Check completo")
        time.sleep(300)

if __name__ == "__main__":
    track_memecoins()
