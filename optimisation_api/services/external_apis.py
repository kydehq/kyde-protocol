# ---------------------------------------------------------------------------
# DATEI 2: optimisation_api/services/external_apis.py
# ---------------------------------------------------------------------------
# Dieser Service ist nur dafür zuständig, mit der Außenwelt zu reden.
# Das macht den Code sauberer und besser testbar.

# Wir holen jetzt die komplette Preisprognose, nicht nur den aktuellen Preis.

import requests
from datetime import datetime, timezone

def get_epex_spot_forecast() -> list[dict] | None:
    """
    Returns a list of all available day-ahead prices for today and tomorrow.
    """
    url = "[https://api.awattar.de/v1/marketdata](https://api.awattar.de/v1/marketdata)"
    try:
        response = requests.get(url, timeout=5) # Timeout leicht reduziert
        response.raise_for_status()
        market_data = response.json()["data"]
        
        forecast = []
        for item in market_data:
            forecast.append({
                "timestamp_utc": datetime.fromtimestamp(item["start_timestamp"] / 1000, tz=timezone.utc),
                "price_eur_kwh": item["marketprice"] / 1000
            })
        return forecast
    except requests.exceptions.RequestException as e:
        print(f"FEHLER: aWATTar API-Anfrage fehlgeschlagen: {e}")
        return None

def get_solar_forecast(hours: int = 6) -> list[float] | None:
    """
    Returns a list of solar radiation forecasts for the next hours.
    """
    # Diese Werte sollten idealerweise auch aus Umgebungsvariablen kommen.
    lat = os.environ.get("LATITUDE", "50.1109")
    lon = os.environ.get("LONGITUDE", "8.6821")
    url = f"[https://api.open-meteo.com/v1/forecast?latitude=](https://api.open-meteo.com/v1/forecast?latitude=){lat}&longitude={lon}&hourly=shortwave_radiation&forecast_days=1"
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()
        now_hour = datetime.now(timezone.utc).hour
        # Stellt sicher, dass die Indizes nicht außerhalb des Bereichs liegen
        return data["hourly"]["shortwave_radiation"][now_hour : now_hour + hours]
    except requests.exceptions.RequestException as e:
        print(f"FEHLER: Open-Meteo API-Anfrage fehlgeschlagen: {e}")
        return None
    except (KeyError, IndexError) as e:
        print(f"FEHLER: Unerwartetes Datenformat von Open-Meteo: {e}")
        return None