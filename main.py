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
from datetime import datetime
import pytz  # pip install pytz

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
ARCHIVO_HISTORICO = "historico_precios.json"

# Inicializaciones
analyzer = SentimentIntensityAnalyzer()

auth = tweepy.OAuth1UserHandler(TWITTER_API_KEY, TWITTER_API_SECRET, TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET)
twitter_api = tweepy.API(auth)

reddit = praw.Reddit(client_id=REDDIT_CLIENT_ID,
                     client_secret=REDDIT_CLIENT_SECRET,
                     user_agent=REDDIT_USER_AGENT)

enviados = set()

# Modelo ML simple (mock)
def entrenar_modelo_mock():
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
    if not fecha_str:
        return 0
    from datetime import datetime
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

def cargar_historico():
    if os.path.exists(ARCHIVO_HISTORICO):
        with open(ARCHIVO_HISTORICO, "r") as f:
            return json.load(f)
    return {}

def guardar_historico(historico):
    with open(ARCHIVO_HISTORICO, "w") as f:
        json.dump(historico, f)

def enviar_resumen_diario():
    tz_cr = pytz.timezone('America/Costa_Rica')
    ahora_utc = datetime.utcnow().replace(tzinfo=pytz.utc)
    ahora_cr = ahora_utc.astimezone(tz_cr)
    fecha_hoy = ahora_cr.strftime("%Y-%m-%d")

    memecoins = obtener_memecoins()
    top10 = obtener_top10_cripto()
    todas_coins = memecoins + top10

    if not todas_coins:
        print("No se obtuvieron datos para el resumen diario.")
        return False

    df_coins = pd.DataFrame(todas_coins)
    precios_hoy = {coin['id']: coin['current_price'] for coin in todas_coins}
    historico = cargar_historico()

    mensaje_resumen = f"📊 *Resumen diario de criptomonedas - {fecha_hoy}*\n\n"

    max_subida = df_coins.loc[df_coins['price_change_percentage_24h'].idxmax()]
    max_bajada = df_coins.loc[df_coins['price_change_percentage_24h'].idxmin()]
    max_volumen = df_coins.loc[df_coins['total_volume'].idxmax()]

    mensaje_resumen += f"🚀 Mayor subida 24h: *{max_subida['name']}* (+{max_subida['price_change_percentage_24h']:.2f}%)\n"
    mensaje_resumen += f"📉 Mayor caída 24h: *{max_bajada['name']}* ({max_bajada['price_change_percentage_24h']:.2f}%)\n"
    mensaje_resumen += f"💸 Mayor volumen 24h: *{max_volumen['name']}* (${int(max_volumen['total_volume']):,})\n\n"

    mensaje_resumen += "🔎 Sentimiento social (Twitter + Reddit) aproximado:\n"
    for coin in todas_coins:
        stw = analizar_sentimiento_twitter(coin['symbol'])
        srd = sentimiento_reddit(coin['symbol'])
        stotal = (stw + srd) / 2
        mensaje_resumen += f"- {coin['name']}: {stotal:.2f}\n"
    mensaje_resumen += "\n"

    df_sorted = df_coins.sort_values(by='price_change_percentage_24h', ascending=False)
    mensaje_resumen += "🏆 Top 3 ganadores:\n"
    for i, row in df_sorted.head(3).iterrows():
        mensaje_resumen += f"  {row['name']}: +{row['price_change_percentage_24h']:.2f}%\n"
    mensaje_resumen += "\n"
    mensaje_resumen += "📉 Top 3 perdedores:\n"
    for i, row in df_sorted.tail(3).iterrows():
        mensaje_resumen += f"  {row['name']}: {row['price_change_percentage_24h']:.2f}%\n"
    mensaje_resumen += "\n"

    market_cap_total = df_coins['market_cap'].sum()
    volumen_total = df_coins['total_volume'].sum()
    mensaje_resumen += f"🌐 Market Cap total: ${int(market_cap_total):,}\n"
    mensaje_resumen += f"📊 Volumen total 24h: ${int(volumen_total):,}\n\n"

    if fecha_hoy in historico:
        prev_prices = historico.get(fecha_hoy, {})
        mensaje_resumen += "🔄 Comparativa precios vs hoy:\n"
        for coin_id, price in precios_hoy.items():
            price_ayer = prev_prices.get(coin_id)
            if price_ayer:
                cambio = (price - price_ayer) / price_ayer * 100
                mensaje_resumen += f"- {coin_id}: {cambio:+.2f}%\n"
    else:
        mensaje_resumen += "No hay datos comparativos de días anteriores.\n"

    enviado = enviar_alerta_telegram(mensaje_resumen)
    if enviado:
        print("Resumen diario enviado a Telegram.")
        historico[fecha_hoy] = precios_hoy
        guardar_historico(historico)
        return True
    else:
        print("Error enviando resumen diario.")
        return False


def main():
    print("🚀 Tracker avanzado MemeCoin + Top10 + ML + Liquidez + Sentimiento social iniciado.")
    compras = cargar_compras()
    global enviados
    tz_cr = pytz.timezone('America/Costa_Rica')
    resumen_enviado_hoy = False

    while True:
        try:
            ahora_utc = datetime.utcnow().replace(tzinfo=pytz.utc)
            ahora_cr = ahora_utc.astimezone(tz_cr)

            # Enviar resumen diario a las 7:00 PM hora Costa Rica
            if ahora_cr.hour == 19 and ahora_cr.minute == 0 and not resumen_enviado_hoy:
                enviado = enviar_resumen_diario()
                if enviado:
                    resumen_enviado_hoy = True

            # Resetear bandera a la 00:01 para el siguiente día
            if ahora_cr.hour == 0 and ahora_cr.minute == 1:
                resumen_enviado_hoy = False

            # Aquí puedes incluir el resto de tu lógica de monitoreo e informes periódicos

            time.sleep(30)

        except Exception as e:
            print(f"Error en loop principal: {e}")
            time.sleep(60)


if __name__ == "__main__":
    main()
