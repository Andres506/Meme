import requests
import os

TOKEN_DETALLE_URL = "https://api.coingecko.com/api/v3/coins/"
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def analizar_token(token_id):
    try:
        url = f"{TOKEN_DETALLE_URL}{token_id}"
        res = requests.get(url)
        if res.status_code != 200:
            return None
        data = res.json()

        nombre = data.get("name")
        symbol = data.get("symbol")
        score = data.get("coingecko_score", 0)
        enlaces = data.get("links", {})
        homepage = enlaces.get("homepage", [""])[0]

        # Criterios para alerta
        if data.get("market_data") and score >= 5:
            return {
                "nombre": nombre,
                "symbol": symbol.upper(),
                "score": score,
                "link": f"https://www.coingecko.com/es/monedas/{token_id}",
                "homepage": homepage
            }
    except Exception as e:
        print("Error al analizar token:", e)
    return None

def enviar_alerta(info):
    try:
        mensaje = (
            f"🚨 *Nueva posible memecoin interesante detectada!*\n\n"
            f"*Nombre:* {info['nombre']} ({info['symbol']})\n"
            f"*Score:* {info['score']}\n"
            f"[Ver en CoinGecko]({info['link']})\n"
        )
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        data = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": mensaje,
            "parse_mode": "Markdown"
        }
        requests.post(url, data=data)
    except Exception as e:
        print("Error al enviar mensaje:", e)
