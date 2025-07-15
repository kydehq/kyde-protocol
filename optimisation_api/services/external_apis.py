# ---------------------------------------------------------------------------
# DATEI 2: optimisation_api/services/external_apis.py
# ---------------------------------------------------------------------------
# Dieser Service ist nur dafür zuständig, mit der Außenwelt zu reden.
# Das macht den Code sauberer und besser testbar.

import requests
from datetime import datetime, timezone

def get_epex_spot_price() -> float | None:
    """Returns current hour day-ahead price in EUR/kWh (aWATTar)."""
    url = "https://api.awattar.de/v1/marketdata"
    try:
        data = requests.get(url, timeout=10).json()["data"]
        now = datetime.now(timezone.utc)
        for item in data:
            ts = datetime.fromtimestamp(item["start_timestamp"] / 1000, tz=timezone.utc)
            if ts.date() == now.date() and ts.hour == now.hour:
                return item["marketprice"] / 1000
    except Exception as exc:
        print(f"aWATTar error: {exc}")
    return None

def get_solar_forecast(hours: int = 6) -> list[float] | None:
    """Return list[float] of W/m² for next `hours` (Open-Meteo)."""
    lat, lon = 50.1109, 8.6821  # TODO: Aus Konfiguration laden
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&hourly=shortwave_radiation&forecast_days=1"
    try:
        data = requests.get(url, timeout=10).json()
        now_hour = datetime.now(timezone.utc).hour
        return data["hourly"]["shortwave_radiation"][now_hour : now_hour + hours]
    except Exception as exc:
        print(f"Open-Meteo error: {exc}")
    return None
