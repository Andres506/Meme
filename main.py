import time
import os
import requests
import tweepy
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

TWITTER_API_KEY = os.getenv("TWITTER_API_KEY")
TWITTER_API_SECRET = os.getenv("TWITTER_API_SECRET")
TWITTER_ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN")
TWITTER_ACCESS_SECRET = os.getenv("TWITTER_ACCESS_SECRET")

COINGECKO_API = "https://api.coingecko.com/api/v3/coins/markets"

MEME_KEYWORDS = ["doge", "shiba", "moon", "elon", "pepe", "meme"]

analyzer = SentimentIntensityAnalyzer()

auth = tweepy.OAuth1UserHandler(TWITTER_API_KEY, TWITTER_API_SECRET, TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET)
twitter_api = tweepy.API(auth)

enviados = set()

def enviar_alerta_telegram(mensaje):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": mensaje,
        "parse_mode": "Markdown"
    }
    response = requests.post(url, data=data)
    return response.ok

def obtener_memecoins():
    params = {
        "vs_currency": "usd",
        "order": "volume_desc",
        "per_page": 100,
        "page": 1,
        "price_change_percentage": "1h,24h"
    }
    r = requests.get(COINGECKO_API, params=params)
    if r.status_code != 200:
        print(f"Error CoinGecko API: {r.status_code}")
        return []
    data = r.json()
    memecoins = []
    for coin in data:
        name = coin.get("name", "").lower()
        if any(k in name for k in MEME_KEYWORDS):
            memecoins.append(coin)
    return memecoins

def obtener_top10_cripto():
    params = {
        "vs_currency": "usd",
        "order": "market_cap_desc",
        "per_page": 10,
        "page": 1,
        "price_change_percentage": "1h,24h"
    }
    r = requests.get(COINGECKO_API, params=params)
    if r.status_code != 200:
        print(f"Error CoinGecko API top10: {r.status_code}")
        return []
    return r.json()

def analizar_sentimiento_twitter(keyword):
    try:
        tweets = twitter_api.search_tweets(q=keyword, count=30, lang="en")
        scores = [analyzer.polarity_scores(tweet.text)['compound'] for tweet in tweets]
        if scores:
            return sum(scores) / len(scores)
        return 0
    except Exception as e:
        print(f"Error en análisis de sentimiento Twitter: {e}")
        return 0

def obtener_liquidez_dex(token_id):
    # Mock simple para iniciar
    return 100000

def detectar_caida_rapida(precio_actual, precio_max_1h):
    if precio_max_1h == 0:
        return False
    caida = (precio_max_1h - precio_actual) / precio_max_1h * 100
    return caida >= 15

def riesgo_final(coin, liquidez, sentimiento, caida):
    vol = coin.get('total_volume', 0)
    mc = coin.get('market_cap', 0)

    if vol < 100_000 or mc < 50_000 or liquidez < 50_000 or sentimiento < -0.3 or caida:
        return "Alto"
    elif vol < 500_000 or mc < 1_000_000 or liquidez < 200_000 or sentimiento < 0:
        return "Medio"
    else:
        return "Bajo"

def recomendar_accion(riesgo, sentimiento, caida):
    if caida:
        return "Vender urgente (posible rugpull)"
    if riesgo == "Alto" or sentimiento < 0:
        return "Vender"
    if riesgo == "Medio" and 0 <= sentimiento <= 0.3:
        return "Mantener"
    if riesgo == "Bajo" and sentimiento > 0.3:
        return "Comprar"
    return "Mantener"

def main():
    print("🚀 MemeCoin + Top10 Crypto Tracker PRO iniciado.")
    while True:
        try:
            memecoins = obtener_memecoins()
            top10 = obtener_top10_cripto()
            todas_coins = {coin['id']: coin for coin in memecoins + top10}

            for coin in todas_coins.values():
                price = coin.get("current_price", 0)
                max_price_1h = price  # Por demo, asumimos precio actual
                liquidez = obtener_liquidez_dex(coin['id'])
                sentimiento = analizar_sentimiento_twitter(coin['symbol'])
                caida = detectar_caida_rapida(price, max_price_1h)
                riesgo = riesgo_final(coin, liquidez, sentimiento, caida)
                accion = recomendar_accion(riesgo, sentimiento, caida)

                if riesgo == "Alto":
                    continue

                if coin['id'] not in enviados:
                    mensaje = (
                        f"🚨 *Nueva criptomoneda detectada* 🚨\n"
                        f"📈 *{coin['name']}* ({coin['symbol'].upper()})\n"
                        f"💰 Precio: ${price:.8f}\n"
                        f"🏦 Market Cap: ${coin.get('market_cap',0):,}\n"
                        f"📊 Volumen 24h: ${coin.get('total_volume',0):,}\n"
                        f"🔹 Liquidez DEX: ${liquidez}\n"
                        f"🔹 Sentimiento Twitter: {sentimiento:.2f}\n"
                        f"⚠️ Caída rápida (rugpull): {'Sí' if caida else 'No'}\n"
                        f"⚠️ Nivel de riesgo: {riesgo}\n"
                        f"💡 Recomendación: *{accion}*\n"
                        f"🔗 [Ver en CoinGecko](https://www.coingecko.com/en/coins/{coin['id']})"
                    )
                    enviado = enviar_alerta_telegram(mensaje)
                    if enviado:
                        print(f"Mensaje enviado para {coin['name']}")
                        enviados.add(coin['id'])
                    else:
                        print(f"Error enviando mensaje para {coin['name']}")

            time.sleep(300)
        except Exception as e:
            print(f"Error principal: {e}")
            time.sleep(60)

if __name__ == "__main__":
    main()
