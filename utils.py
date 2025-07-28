import requests
import json
from datetime import datetime

URL = "https://api.coingecko.com/api/v3/coins/markets"
ALERTAS_FILE = "alertas.json"

def obtener_tendencias():
    params = {
        "vs_currency": "usd",
        "order": "volume_desc",
        "per_page": 100,
        "page": 1,
        "price_change_percentage": "1h,24h"
    }
    r = requests.get(URL, params=params)
    return r.json()

def formatear_mensaje(nombre, simbolo, precio, cambio_1h, cambio_24h, volumen, id, señal):
    return (
        f"{señal} {nombre} ({simbolo})\n"
        f"💵 Precio: ${precio:.6f}\n"
        f"📈 1h: {cambio_1h:.2f}% | 24h: {cambio_24h:.2f}%\n"
        f"🔊 Volumen 24h: ${volumen:,.0f}\n"
        f"🔗 https://www.coingecko.com/es/monedas/{id}"
    )

def ya_alertado(nombre):
    try:
        with open(ALERTAS_FILE, "r") as f:
            datos = json.load(f)
    except FileNotFoundError:
        return False

    return nombre in datos

def guardar_alerta(nombre):
    try:
        with open(ALERTAS_FILE, "r") as f:
            datos = json.load(f)
    except FileNotFoundError:
        datos = []

    datos.append(nombre)
    with open(ALERTAS_FILE, "w") as f:
        json.dump(datos, f)
