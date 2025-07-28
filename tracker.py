# tracker.py
import requests
from datetime import datetime, timedelta

# Filtrar tokens tipo meme por nombre
MEME_KEYWORDS = ["doge", "elon", "pepe", "shib", "baby", "moon", "floki", "bonk", "wojak", "inu"]

# Reemplazar con tu API key de GeckoTerminal o DEXTools (según la API que se use)
API_KEY = "TU_API_KEY_AQUI"


def get_recent_tokens_geckoterminal():
    url = "https://api.geckoterminal.com/api/v2/networks/eth/tokens"
    params = {"include": "recent"}  # Puedes modificar para otras redes o criterios
    response = requests.get(url, params=params)

    if response.status_code != 200:
        print("Error obteniendo tokens recientes")
        return []

    tokens = response.json().get("data", [])
    filtered = []

    for token in tokens:
        attributes = token.get("attributes", {})
        name = attributes.get("name", "").lower()
        volume_usd = float(attributes.get("volume_usd", 0))
        liquidity_usd = float(attributes.get("liquidity_usd", 0))
        price_change_1h = float(attributes.get("price_percent_change_1h", 0))
        buy_ratio = float(attributes.get("buy_ratio", 0)) if attributes.get("buy_ratio") else 0
        holders = int(attributes.get("holders", 0))

        if any(kw in name for kw in MEME_KEYWORDS):
            if liquidity_usd > 10000 and volume_usd > 5000 and holders > 100:
                if price_change_1h > 80 or buy_ratio > 0.8:
                    filtered.append({
                        "name": attributes.get("name"),
                        "symbol": attributes.get("symbol"),
                        "price": attributes.get("price_usd"),
                        "volume": volume_usd,
                        "liquidity": liquidity_usd,
                        "holders": holders,
                        "url": f"https://www.geckoterminal.com/eth/pools/{token.get('id')}"
                    })

    return filtered


if __name__ == "__main__":
    tokens = get_recent_tokens_geckoterminal()
    for t in tokens:
        print(f"Token candidato: {t['name']} ({t['symbol']}) | Volumen: ${t['volume']} | Precio: ${t['price']}")
