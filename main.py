import requests
import time
from utils import formatear_mensaje, ya_alertado, guardar_alerta, obtener_tendencias
from os import getenv
import logging

TOKEN = getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = getenv("TELEGRAM_CHAT_ID")

def enviar_mensaje(texto):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": texto})

def analizar_moneda(coin):
    nombre = coin.get("name", "")
    simbolo = coin.get("symbol", "").upper()
    precio = coin.get("current_price", 0)
    cambio_1h = coin.get("price_change_percentage_1h_in_currency", 0)
    cambio_24h = coin.get("price_change_percentage_24h", 0)
    volumen = coin.get("total_volume", 0)
    id = coin.get("id", "")
    
    if not all([nombre, simbolo, precio, id]):
        return None

    if volumen < 100000:
        return None

    # Clasificación de señal
    if cambio_1h >= 15 or cambio_24h >= 15:
        señal = "🟢 COMPRAR"
    elif cambio_24h < -10:
        señal = "🔴 VENDER"
    else:
        señal = "🟡 MANTENER"

    mensaje = formatear_mensaje(nombre, simbolo, precio, cambio_1h, cambio_24h, volumen, id, señal)

    if not ya_alertado(nombre):
        guardar_alerta(nombre)
        return mensaje
    elif señal == "🔴 VENDER":
        return f"⚠️ {nombre} ha bajado >10%. Señal: {señal}"

    return None

def main():
    logging.basicConfig(level=logging.INFO)
    while True:
        try:
            tendencias = obtener_tendencias()
            for coin in tendencias:
                mensaje = analizar_moneda(coin)
                if mensaje:
                    enviar_mensaje(mensaje)
                    logging.info(f"Alerta enviada: {mensaje}")
        except Exception as e:
            logging.error(f"Error en ejecución: {e}")
        time.sleep(300)  # Esperar 5 minutos

if __name__ == "__main__":
    main()
