# ---------------------------------------------------------------------------
# DATEI 2: optimisation_api/services/external_apis.py
# ---------------------------------------------------------------------------
# Dieser Service ist nur dafür zuständig, mit der Außenwelt zu reden.
# Das macht den Code sauberer und besser testbar.

# Wir holen jetzt die komplette Preisprognose, nicht nur den aktuellen Preis.

# KORRIGIERT: Markdown aus URLs entfernt.
# ---------------------------------------------------------------------------
# VERBESSERT: Fehlerbehandlung erweitert, um Abstürze zu verhindern.
# ---------------------------------------------------------------------------
import requests
from datetime import datetime, timezone
import os
import json # Import für JSONDecodeError

def get_epex_spot_forecast() -> list[dict] | None:
    """
    Returns a list of all available day-ahead prices for today and tomorrow.
    This function is now more robust against API errors.
    """
    url = "https://api.awattar.de/v1/marketdata"
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()  # Raises an exception for 4xx/5xx status codes
        market_data = response.json()["data"]
        
        forecast = []
        for item in market_data:
            # Basic validation for required keys
            if "start_timestamp" in item and "marketprice" in item:
                forecast.append({
                    "timestamp_utc": datetime.fromtimestamp(item["start_timestamp"] / 1000, tz=timezone.utc),
                    "price_eur_kwh": item["marketprice"] / 1000
                })
        return forecast
    except Exception as e:
        # Catches connection errors, timeouts, invalid JSON, missing keys, etc.
        print(f"FEHLER: aWATTar API-Anfrage oder Datenverarbeitung fehlgeschlagen. Fehler: {e}")
        return None

def get_solar_forecast(hours: int = 6) -> list[float] | None:
    """
    Returns a list of solar radiation forecasts for the next hours.
    This function is now more robust against API errors.
    """
    lat = os.environ.get("LATITUDE", "50.1109")
    lon = os.environ.get("LONGITUDE", "8.6821")
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&hourly=shortwave_radiation&forecast_days=1&timezone=UTC"
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()
        now_hour = datetime.now(timezone.utc).hour
        # Basic validation for required keys
        if "hourly" in data and "shortwave_radiation" in data["hourly"]:
             return data["hourly"]["shortwave_radiation"][now_hour : now_hour + hours]
        else:
             print("FEHLER: Unerwartetes Datenformat von Open-Meteo: 'hourly' oder 'shortwave_radiation' fehlt.")
             return None
    except Exception as e:
        # Catches connection errors, timeouts, invalid JSON, missing keys, etc.
        print(f"FEHLER: Open-Meteo API-Anfrage oder Datenverarbeitung fehlgeschlagen. Fehler: {e}")
        return None
