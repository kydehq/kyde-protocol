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
# KORRIGIERT: Funktion get_solar_forecast akzeptiert jetzt lat und lon
# ---------------------------------------------------------------------------
import httpx
from datetime import datetime, timezone
import os

async def get_epex_spot_forecast() -> list[dict] | None:
    url = "https://api.awattar.de/v1/marketdata"
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=5.0)
            response.raise_for_status()
            market_data = response.json()["data"]
        return [{"timestamp_utc": datetime.fromtimestamp(i["start_timestamp"] / 1000, tz=timezone.utc), "price_eur_kwh": i["marketprice"] / 1000} for i in market_data if "start_timestamp" in i and "marketprice" in i]
    except Exception as e:
        print(f"FEHLER: aWATTar API (async) fehlgeschlagen: {e}")
        return None

async def get_solar_forecast(lat: float, lon: float, hours: int = 6) -> list[float] | None:
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&hourly=shortwave_radiation&forecast_days=1&timezone=UTC"
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=5.0)
            response.raise_for_status()
            data = response.json()
        now_hour = datetime.now(timezone.utc).hour
        if "hourly" in data and "shortwave_radiation" in data["hourly"]:
             return data["hourly"]["shortwave_radiation"][now_hour : now_hour + hours]
        else: return None
    except Exception as e:
        print(f"FEHLER: Open-Meteo API (async) fehlgeschlagen: {e}")
        return None
