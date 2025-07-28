import requests
import time
import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

COINGECKO_API = "https://api.coingecko.com/api/v3/coins/markets"

HEADERS = {
    "accept": "application/json"
}

MEME_KEYWORDS = ["doge", "shiba", "moon", "elon", "pepe", "memecoin", "meme"]

enviados = set()

def enviar_mensaje(texto):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": texto,
        "parse_mode": "Markdown"
    }
    response = requests.post(url, data=data)
    return response.ok

def filtrar_y_analizar(data):
    oportunidades = []
    for coin in data:
        name = coin.get("name", "")
        symbol = coin.get("symbol", "").upper()
        price = coin.get("current_price", 0)
        market_cap = coin.get("market_cap", 0)
        volume = coin.get("total_volume", 0)
        id_ = coin.get("id", "")
        change_1h = coin.get("price_change_percentage_1h_in_currency") or 0
        change_24h = coin.get("price_change_percentage_24h") or 0

        # Filtro de palabras clave (memecoin o trashcoin)
        if not any(k in name.lower() for k in MEME_KEYWORDS):
            continue

        # Filtro de liquidez y market cap
        if market_cap is None or volume is None:
            continue
        if not (20_000 <= market_cap <= 10_000_000):
            continue
        if volume < 50_000:
            continue
        if price > 1:
            continue

        # Clasificador de riesgo
        if volume < 100_000 or market_cap < 50_000:
            risk_level = "🔴 Alto"
        elif 100_000 <= volume <= 500_000:
            risk_level = "🟡 Medio"
        else:
            risk_level = "🟢 Bajo"

        oportunidades.append({
            "name": name,
            "symbol": symbol,
            "price": price,
            "market_cap": market_cap,
            "volume": volume,
            "id": id_,
            "change_1h": change_1h,
            "change_24h": change_24h,
            "risk_level": risk_level
        })

    return oportunidades

def main():
    print("🚀 MemeCoin Tracker con filtro y riesgo iniciado.")
    while True:
        try:
            params = {
                "vs_currency": "usd",
                "order": "volume_desc",
                "per_page": 100,
                "page": 1,
                "price_change_percentage": "1h,24h"
            }
            response = requests.get(COINGECKO_API, params=params, headers=HEADERS)
            if response.status_code != 200:
                print(f"Error API CoinGecko: {response.status_code}")
                time.sleep(60)
                continue

            data = response.json()
            oportunidades = filtrar_y_analizar(data)

            for coin in oportunidades:
                unique_id = coin["id"]
                if unique_id not in enviados:
                    mensaje = (
                        f"🚨 *Nueva memecoin detectada* 🚨\n"
                        f"📈 *{coin['name']}* ({coin['symbol']})\n"
                        f"💰 Precio: ${coin['price']:.8f}\n"
                        f"🏦 Market Cap: ${coin['market_cap']:,}\n"
                        f"📊 Volumen 24h: ${coin['volume']:,}\n"
                        f"📉 Cambio 1h: {coin['change_1h']:.2f}% | 24h: {coin['change_24h']:.2f}%\n"
                        f"⚠️ Nivel de riesgo: {coin['risk_level']}\n"
                        f"🔗 [Ver en CoinGecko](https://www.coingecko.com/en/coins/{unique_id})"
                    )
                    enviado = enviar_mensaje(mensaje)
                    if enviado:
                        print(f"Mensaje enviado: {coin['name']}")
                        enviados.add(unique_id)
                    else:
                        print(f"Error al enviar mensaje: {coin['name']}")

            time.sleep(300)  # Esperar 5 minutos
        except Exception as e:
            print(f"Error inesperado: {e}")
            time.sleep(60)

if __name__ == "__main__":
    main()
