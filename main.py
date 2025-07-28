# main.py
import requests
import time
from utils import analizar_token, enviar_alerta

COINGECKO_API = "https://api.coingecko.com/api/v3/coins/list"
TOKEN_CHECK_INTERVAL = 60 * 10  # 10 minutos


def obtener_tokens():
    response = requests.get(COINGECKO_API)
    if response.status_code == 200:
        return response.json()
    return []


def main():
    print("⏳ Iniciando tracker de memecoins...")
    tokens_previos = set()

    while True:
        tokens_actuales = obtener_tokens()
        nuevos_tokens = [t for t in tokens_actuales if t['id'] not in tokens_previos]

        for token in nuevos_tokens:
            info = analizar_token(token['id'])
            if info:
                enviar_alerta(info)

        tokens_previos = set([t['id'] for t in tokens_actuales])
        time.sleep(TOKEN_CHECK_INTERVAL)


if __name__ == "__main__":
    main()
