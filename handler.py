import os
import requests
from fastapi import FastAPI, HTTPException
from datetime import datetime, timezone

# Wir initialisieren die FastAPI-App
# Das ist unser dauerhaft laufender Server
app = FastAPI()

# --- DATENABRUF-FUNKTIONEN ---
# Test-Kommentar

def get_epex_spot_price():
    """Fragt den aktuellen stündlichen EPEX Spot Preis ab."""
    api_url = 'https://api.awattar.de/v1/marketdata'
    try:
        response = requests.get(api_url, timeout=10)
        response.raise_for_status()
        market_data = response.json()['data']
        now_utc = datetime.now(timezone.utc)
        for price_point in market_data:
            start_time = datetime.fromtimestamp(price_point['start_timestamp'] / 1000, tz=timezone.utc)
            if start_time.hour == now_utc.hour and start_time.date() == now_utc.date():
                price_eur_per_kwh = price_point['marketprice'] / 1000
                return price_eur_per_kwh
        return None # Falls kein Preis gefunden wurde
    except Exception as e:
        print(f"Fehler bei aWATTar API: {e}")
        return None

def get_solar_forecast():
    """
    Fragt eine Solar-Wettervorhersage von Open-Meteo ab.
    KOSTENLOS UND OHNE API-KEY!
    Wir fragen die Strahlung für die nächsten 6 Stunden ab.
    Ein Wert > 100 W/m² ist gut, > 500 W/m² ist sehr gut.
    """
    # Beispiel-Koordinaten für Frankfurt, Deutschland. Diese sollten konfigurierbar sein.
    latitude = 50.1109
    longitude = 8.6821
    api_url = f"https://api.open-meteo.com/v1/forecast?latitude={latitude}&longitude={longitude}&hourly=shortwave_radiation&forecast_days=1"
    
    try:
        response = requests.get(api_url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        # Finde die aktuelle Stunde und die nächsten 5 Stunden
        now_hour = datetime.now(timezone.utc).hour
        # Die Strahlungswerte für die nächsten 6 Stunden
        upcoming_radiation = data['hourly']['shortwave_radiation'][now_hour : now_hour + 6]
        return upcoming_radiation
    except Exception as e:
        print(f"Fehler bei Open-Meteo API: {e}")
        return None

# --- DER API-ENDPUNKT ---

@app.get("/entscheidung")
async def get_charging_decision(soc: float):
    """
    Dieser Endpunkt wird von der Tuya-Cloud aufgerufen.
    Er nimmt den aktuellen Batteriestand (State of Charge, SoC) in Prozent entgegen.
    Beispielaufruf: https://dein-dienst.railway.app/entscheidung?soc=55.5
    """
    if not (0.0 <= soc <= 100.0):
        raise HTTPException(status_code=400, detail="SoC muss zwischen 0 und 100 liegen.")

    # 1. Alle benötigten Daten abrufen
    grid_price = get_epex_spot_price()
    solar_forecast = get_solar_forecast()

    if grid_price is None or solar_forecast is None:
        raise HTTPException(status_code=503, detail="Externe Daten konnten nicht abgerufen werden.")

    # 2. Die ENTSCHEIDUNGS-LOGIK (Hier kommt die Intelligenz rein)
    # Dies ist ein einfaches Beispiel. Die Tuya-Entwickler können dies verfeinern.
    
    decision = "DO_NOTHING"
    reason = "Standard-Entscheidung"
    
    # Summe der erwarteten Solarstrahlung für die nächsten 3 Stunden
    next_3h_solar = sum(solar_forecast[0:3])

    # Beispiel-Regel 1: Sehr billig laden
    if grid_price <= 0.05 and soc < 95:
        decision = "CHARGE_FROM_GRID"
        reason = f"Netzpreis ist extrem niedrig ({grid_price:.4f} EUR/kWh)."

    # Beispiel-Regel 2: Bei teurem Strom und voller Batterie entladen
    elif grid_price >= 0.25 and soc > 20:
        decision = "DISCHARGE_TO_HOUSE"
        reason = f"Netzpreis ist hoch ({grid_price:.4f} EUR/kWh), Batterie wird genutzt."
        
    # Beispiel-Regel 3: Auf Solarstrom warten
    elif soc < 80 and next_3h_solar > 300: # Wenn in den nächsten 3h viel Sonne kommt
        decision = "WAIT_FOR_SOLAR"
        reason = f"Es wird bald genug Solarstrom erwartet (Index: {next_3h_solar})."

    # 3. Eine klare JSON-Antwort zurückgeben
    return {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "input_soc_percent": soc,
        "data": {
            "grid_price_eur_per_kwh": grid_price,
            "next_6h_solar_radiation_w_per_m2": solar_forecast
        },
        "decision": {
            "action": decision,
            "reason": reason
        }
    }

