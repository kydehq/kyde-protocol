import os
import requests
from fastapi import FastAPI, HTTPException, Security
from fastapi.security import APIKeyHeader
from datetime import datetime, timezone
from pydantic import BaseModel, Field # pydantic wird mit FastAPI installiert

# --- Konfiguration & Modelle ---

# Wir definieren ein Modell für unsere Antwort. Das hilft bei der Dokumentation.
class DecisionResponse(BaseModel):
    timestamp_utc: datetime
    input_soc_percent: float
    data: dict
    decision: dict

# API-Schlüssel-Konfiguration für die Sicherheit
API_KEY_NAME = "X-API-KEY"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=True)

app = FastAPI()

# --- HILFSFUNKTIONEN & KONFIGURATION ---

def get_config(var_name: str, default_value: str) -> str:
    """Holt eine Umgebungsvariable oder gibt einen Fehler zurück."""
    value = os.environ.get(var_name)
    if value is None:
        print(f"WARNUNG: Umgebungsvariable {var_name} nicht gefunden, nutze Standardwert: {default_value}")
        return default_value
    return value

# Lade die Konfiguration beim Start der App
LATITUDE = float(get_config("LATITUDE", "50.1109"))
LONGITUDE = float(get_config("LONGITUDE", "8.6821"))
PRICE_THRESHOLD_LOW = float(get_config("PRICE_THRESHOLD_LOW", "0.05"))
PRICE_THRESHOLD_HIGH = float(get_config("PRICE_THRESHOLD_HIGH", "0.25"))
SOLAR_THRESHOLD_HIGH = int(get_config("SOLAR_THRESHOLD_HIGH", "300"))
INTERNAL_API_KEY = get_config("INTERNAL_API_KEY", "ein-sehr-geheimes-passwort")


async def get_api_key(api_key: str = Security(api_key_header)):
    """Überprüft den mitgesendeten API-Schlüssel."""
    if api_key != INTERNAL_API_KEY:
        raise HTTPException(status_code=403, detail="Ungültiger oder fehlender API-Schlüssel")

# --- DATENABRUF-FUNKTIONEN ---

def get_epex_spot_price():
    # ... (Funktion bleibt unverändert)
    api_url = 'https://api.awattar.de/v1/marketdata'
    try:
        response = requests.get(api_url, timeout=10)
        response.raise_for_status()
        market_data = response.json()['data']
        now_utc = datetime.now(timezone.utc)
        for price_point in market_data:
            start_time = datetime.fromtimestamp(price_point['start_timestamp'] / 1000, tz=timezone.utc)
            if start_time.hour == now_utc.hour and start_time.date() == now_utc.date():
                return price_point['marketprice'] / 1000
        return None
    except Exception:
        return None

def get_solar_forecast():
    # ... (Funktion nutzt jetzt die Konfigurationsvariablen)
    api_url = f"https://api.open-meteo.com/v1/forecast?latitude={LATITUDE}&longitude={LONGITUDE}&hourly=shortwave_radiation&forecast_days=1"
    try:
        response = requests.get(api_url, timeout=10)
        response.raise_for_status()
        data = response.json()
        now_hour = datetime.now(timezone.utc).hour
        return data['hourly']['shortwave_radiation'][now_hour : now_hour + 6]
    except Exception:
        return None

# --- DER GESICHERTE API-ENDPUNKT ---

@app.get("/entscheidung", response_model=DecisionResponse)
async def get_charging_decision(soc: float, api_key: str = Security(get_api_key)):
    """
    Dieser Endpunkt wird von der Tuya-Cloud aufgerufen.
    Er nimmt den aktuellen Batteriestand (SoC) entgegen und ist durch einen API-Schlüssel geschützt.
    """
    if not (0.0 <= soc <= 100.0):
        raise HTTPException(status_code=400, detail="SoC muss zwischen 0 und 100 liegen.")

    grid_price = get_epex_spot_price()
    solar_forecast = get_solar_forecast()

    if grid_price is None or solar_forecast is None:
        raise HTTPException(status_code=503, detail="Externe Daten (Strompreis/Wetter) konnten nicht abgerufen werden.")

    # --- VERBESSERTE ENTSCHEIDUNGS-LOGIK ---
    decision = "DO_NOTHING"
    reason = "Standard: Keine Aktion nötig."
    next_3h_solar = sum(solar_forecast[0:3])

    # Priorität 1: Sicherheitsregeln
    if soc < 10:
        decision = "CHARGE_FROM_GRID"
        reason = "Sicherheit: Batterie fast leer, laden um Tiefentladung zu verhindern."
    elif soc > 98:
        decision = "DO_NOTHING"
        reason = "Sicherheit: Batterie fast voll, Ladevorgang gestoppt."
    
    # Priorität 2: Auf Gelegenheiten reagieren (nur wenn keine Sicherheitsregel greift)
    else:
        # Regel A: Extrem billiger Strom -> Immer laden (wenn nicht voll)
        if grid_price <= PRICE_THRESHOLD_LOW and soc < 95:
            decision = "CHARGE_FROM_GRID"
            reason = f"Gelegenheit: Netzpreis ist extrem niedrig ({grid_price:.4f} EUR/kWh)."
        
        # Regel B: Viel Sonne kommt -> Warten, nicht aus dem Netz laden
        elif soc < 80 and next_3h_solar > SOLAR_THRESHOLD_HIGH:
            decision = "WAIT_FOR_SOLAR"
            reason = f"Strategie: Es wird bald genug Solarstrom erwartet (Index: {next_3h_solar})."
            
        # Regel C: Teurer Strom -> Entladen
        elif grid_price >= PRICE_THRESHOLD_HIGH and soc > 20:
            decision = "DISCHARGE_TO_HOUSE"
            reason = f"Kosten sparen: Netzpreis ist hoch ({grid_price:.4f} EUR/kWh), Batterie wird genutzt."

    return {
        "timestamp_utc": datetime.now(timezone.utc),
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

