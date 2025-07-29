import time
import os
import json
import requests
import tweepy
import praw
import pandas as pd
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from dotenv import load_dotenv
from sklearn.ensemble import RandomForestClassifier
from datetime import datetime, timedelta

load_dotenv()

# --- Configuraciones ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

TWITTER_API_KEY = os.getenv("TWITTER_API_KEY")
TWITTER_API_SECRET = os.getenv("TWITTER_API_SECRET")
TWITTER_ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN")
TWITTER_ACCESS_SECRET = os.getenv("TWITTER_ACCESS_SECRET")

REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET")
REDDIT_USER_AGENT = "meme_coin_tracker_bot"

COINGECKO_API = "https://api.coingecko.com/api/v3/coins/markets"

MEME_KEYWORDS = ["doge", "shiba", "moon", "elon", "pepe", "meme"]

ARCHIVO_COMPRAS = "compras.json"

# --- Inicialización ---

analyzer = SentimentIntensityAnalyzer()

auth = tweepy.OAuth1UserHandler(TWITTER_API_KEY, TWITTER_API_SECRET, TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET)
twitter_api = tweepy.API(auth)

reddit = praw.Reddit(client_id=REDDIT_CLIENT_ID,
                     client_secret=REDDIT_CLIENT_SECRET,
                     user_agent=REDDIT_USER_AGENT)

enviados = set()

# Modelo ML: por simplicidad entrenamos con datos mock aquí (en real, entrenar offline)
def entrenar_modelo_mock():
    # Datos sintéticos ejemplo
    df = pd.DataFrame({
        'volumen': [100000, 500000, 2000000, 300000, 40000],
        'cambio_24h': [10, -5, 25, 0, -20],
        'sentimiento': [0.5, -0.1, 0.8, 0.2, -0.5],
        'edad_contrato': [10, 20, 5, 15, 30],
        'exito': [1, 0, 1, 0, 0]
    })
    X = df[['volumen', 'cambio_24h', 'sentimiento', 'edad_contrato']]
    y = df['exito']
    modelo = RandomForestClassifier(n_estimators=100, random_state=42)
    modelo.fit(X, y)
    return modelo

modelo = entrenar_modelo_mock()

def enviar_alerta_telegram(mensaje):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": mensaje,
        "parse_mode": "Markdown"
    }
    r = requests.post(url, data=data)
    return r.ok

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
        print(f"Error análisis Twitter: {e}")
        return 0

def sentimiento_reddit(keyword, subreddit="CryptoCurrency", limit=30):
    try:
        posts = reddit.subreddit(subreddit).search(keyword, limit=limit)
        scores = []
        for post in posts:
            scores.append(analyzer.polarity_scores(post.title)['compound'])
        if scores:
            return sum(scores) / len(scores)
        return 0
    except Exception as e:
        print(f"Error análisis Reddit: {e}")
        return 0

def obtener_liquidez_pancakeswap(token_address):
    url = f"https://api.pancakeswap.info/api/v2/tokens/{token_address}"
    try:
        r = requests.get(url)
        if r.status_code == 200:
            data = r.json()
            market_cap = data.get('data', {}).get('marketCap', 0)
            return float(market_cap)
        else:
            return 0
    except:
        return 0

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

# Alertas Take Profit / Stop Loss
def cargar_compras():
    if os.path.exists(ARCHIVO_COMPRAS):
        with open(ARCHIVO_COMPRAS, "r") as f:
            return json.load(f)
    return {}

def guardar_compras(compras):
    with open(ARCHIVO_COMPRAS, "w") as f:
        json.dump(compras, f)

def check_alertas_tp_sl(compras, coin_id, precio_actual):
    if coin_id not in compras:
        return None
    precio_compra = compras[coin_id]["precio_compra"]
    ganancia = (precio_actual - precio_compra) / precio_compra * 100
    if ganancia >= 20:
        return "Alerta: Tomar ganancias (+20%)"
    elif ganancia <= -10:
        return "Alerta: Minimizar pérdidas (-10%)"
    return None

def calcular_edad_contrato(fecha_str):
    # Suponiendo fecha_str tipo "2021-06-15"
    if not fecha_str:
        return 0
    try:
        fecha = datetime.strptime(fecha_str, "%Y-%m-%d")
        hoy = datetime.utcnow()
        return (hoy - fecha).days
    except:
        return 0

def predecir_potencial(modelo, datos):
    df_pred = pd.DataFrame([datos])
    pred = modelo.predict(df_pred)
    return pred[0] == 1

def enviar_reporte_diario():
    try:
        top_memecoins = sorted(obtener_memecoins(), key=lambda x: x.get('price_change_percentage_24h', 0), reverse=True)[:10]
        top_criptos = obtener_top10_cripto()

        mensaje = "*📊 Reporte Diario de Criptomonedas (6:10 PM)*\n\n"
        mensaje += "*🐶 Top 10 Memecoins del Día:*\n"
        for i, coin in enumerate(top_memecoins, 1):
            mensaje += f"{i}. {coin['name']} ({coin['symbol'].upper()}) - ${coin['current_price']:.6f} ({coin.get('price_change_percentage_24h', 0):+.2f}%)\n"

        mensaje += "\n*💎 Top Criptos por Market Cap:*\n"
        for i, coin in enumerate(top_criptos, 1):
            mensaje += f"{i}. {coin['name']} ({coin['symbol'].upper()}) - ${coin['current_price']:.2f} ({coin.get('price_change_percentage_24h', 0):+.2f}%)\n"

        enviar_alerta_telegram(mensaje)
        print("✅ Reporte diario enviado.")
    except Exception as e:
        print(f"❌ Error al enviar reporte diario: {e}")

def main():
    print("🚀 Tracker avanzado MemeCoin + Top10 + ML + Liquidez + Sentimiento social iniciado.")
    compras = cargar_compras()
    global enviados
    reporte_enviado = False  # Control para enviar solo una vez al día
    while True:
        try:
            memecoins = obtener_memecoins()
            top10 = obtener_top10_cripto()
            todas_coins = {coin['id']: coin for coin in memecoins + top10}

            for coin in todas_coins.values():
                price = coin.get("current_price", 0)
                max_price_1h = price  # Demo
                contract_address = coin.get('contract_address') or coin.get('platforms', {}).get('ethereum') or ''

                liquidez = obtener_liquidez_pancakeswap(contract_address) if contract_address else 0
                sentimiento_twitter = analizar_sentimiento_twitter(coin['symbol'])
                sentimiento_reddit = sentimiento_reddit(coin['symbol'])
                sentimiento_total = (sentimiento_twitter + sentimiento_reddit) / 2

                caida = detectar_caida_rapida(price, max_price_1h)
                riesgo = riesgo_final(coin, liquidez, sentimiento_total, caida)
                accion = recomendar_accion(riesgo, sentimiento_total, caida)

                # Check ML potencial
                edad = calcular_edad_contrato(coin.get('genesis_date'))
                datos_ml = {
                    'volumen': coin.get('total_volume', 0),
                    'cambio_24h': coin.get('price_change_percentage_24h', 0),
                    'sentimiento': sentimiento_total,
                    'edad_contrato': edad
                }
                tiene_potencial = predecir_potencial(modelo, datos_ml)

                # Check alertas TP/SL
                alerta_tp_sl = check_alertas_tp_sl(compras, coin['id'], price)

                # Construir mensaje solo si riesgo no alto
                if riesgo != "Alto":
                    mensaje = (
                        f"🚨 *Cripto detectada* 🚨\n"
                        f"📈 *{coin['name']}* ({coin['symbol'].upper()})\n"
                        f"💰 Precio: ${price:.8f}\n"
                        f"🏦 Market Cap: ${coin.get('market_cap',0):,}\n"
                        f"📊 Volumen 24h: ${coin.get('total_volume',0):,}\n"
                        f"🔹 Liquidez DEX (proxy): ${liquidez:.2f}\n"
                        f"🔹 Sentimiento total: {sentimiento_total:.2f}\n"
                        f"⚠️ Caída rápida: {'Sí' if caida else 'No'}\n"
                        f"⚠️ Riesgo: {riesgo}\n"
                        f"💡 Recomendación: *{accion}*\n"
                        f"🤖 ML Potencial: {'Alto' if tiene_potencial else 'Bajo'}\n"
                        f"{f'⚠️ {alerta_tp_sl}' if alerta_tp_sl else ''}\n"
                        f"🔗 [Ver CoinGecko](https://www.coingecko.com/en/coins/{coin['id']})"
                    )
                    if coin['id'] not in enviados:
                        enviado = enviar_alerta_telegram(mensaje)
                        if enviado:
                            print(f"Mensaje enviado: {coin['name']}")
                            enviados.add(coin['id'])

                            # Si recomendación es comprar y no está en compras, agregar
                            if accion == "Comprar" and coin['id'] not in compras:
                                compras[coin['id']] = {"precio_compra": price}
                                guardar_compras(compras)

            # Envío diario a las 18:10 (UTC-5 Colombia/México)
            ahora = datetime.utcnow() - timedelta(hours=6)
            if ahora.hour == 18 and ahora.minute == 10:
                if not reporte_enviado:
                    enviar_reporte_diario()
                    reporte_enviado = True
            else:
                reporte_enviado = False  # Reset para el próximo día

            time.sleep(60)  # Dormir 1 minuto para control horario y no saturar

        except Exception as e:
            print(f"Error en loop principal: {e}")
            time.sleep(60)

if __name__ == "__main__":
    main()
