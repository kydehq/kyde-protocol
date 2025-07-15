# ---------------------------------------------------------------------------
# DATEI 2: optimisation_api/services/external_apis.py
# ---------------------------------------------------------------------------
# Dieser Service ist nur dafür zuständig, mit der Außenwelt zu reden.
# Das macht den Code sauberer und besser testbar.

# Wir holen jetzt die komplette Preisprognose, nicht nur den aktuellen Preis.

import requests
from datetime import datetime, timezone, timedelta

def get_epex_spot_forecast() -> list[dict] | None:
    """
    Returns a list of all available day-ahead prices for today and tomorrow.
    Each item is a dict: {'timestamp_utc': datetime, 'price_eur_kwh': float}
    """
    url = "https://api.awattar.de/v1/marketdata"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        market_data = response.json()["data"]
        
        forecast = []
        for item in market_data:
            forecast.append({
                "timestamp_utc": datetime.fromtimestamp(item["start_timestamp"] / 1000, tz=timezone.utc),
                "price_eur_kwh": item["marketprice"] / 1000
            })
        return forecast
    except Exception as exc:
        print(f"aWATTar forecast error: {exc}")
        return None

def get_solar_forecast(hours: int = 6) -> list[float] | None:
    # ... (Funktion bleibt unverändert)
    lat, lon = 50.1109, 8.6821
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&hourly=shortwave_radiation&forecast_days=1"
    try:
        data = requests.get(url, timeout=10).json()
        now_hour = datetime.now(timezone.utc).hour
        return data["hourly"]["shortwave_radiation"][now_hour : now_hour + hours]
    except Exception as exc:
        print(f"Open-Meteo error: {exc}")
        return None