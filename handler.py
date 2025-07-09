import os
import requests
from fastapi import FastAPI, HTTPException, Security
from fastapi.security import APIKeyHeader
from datetime import datetime, timezone
from pydantic import BaseModel
import psycopg2

# --- Konfiguration & Modelle ---

class DecisionResponse(BaseModel):
    timestamp_utc: datetime
    input_soc_percent: float
    data: dict
    decision: dict

API_KEY_NAME = "X-API-KEY"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=True)

app = FastAPI()

# --- HILFSFUNKTIONEN & KONFIGURATION ---

def get_config(var_name: str, default_value: str = None) -> str:
    value = os.environ.get(var_name)
    if value is None:
        if default_value is None:
            raise ValueError(f"FEHLER: Essentielle Umgebungsvariable {var_name} nicht gefunden!")
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
DATABASE_URL = get_config("DATABASE_URL")
# NEU: Die Preiszone für aWATTar konfigurierbar machen
AWATTAR_MARKET = get_config("AWATTAR_MARKET", "DE-LU")


def setup_database():
    # ... (Funktion bleibt unverändert)
    conn = None
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS decisions (
                id SERIAL PRIMARY KEY,
                timestamp_utc TIMESTAMPTZ NOT NULL,
                grid_price REAL,
                solar_forecast_w_m2 TEXT,
                input_soc REAL,
                decision_action VARCHAR(50),
                decision_reason TEXT
            );
        """)
        conn.commit()
        cursor.close()
        print("Datenbank-Tabelle 'decisions' ist bereit.")
    except Exception as e:
        print(f"Fehler beim Einrichten der Datenbank: {e}")
    finally:
        if conn:
            conn.close()

setup_database()

async def get_api_key(api_key: str = Security(api_key_header)):
    if api_key != INTERNAL_API_KEY:
        raise HTTPException(status_code=403, detail="Ungültiger oder fehlender API-Schlüssel")

# --- DATENABRUF-FUNKTIONEN ---

def get_epex_spot_price():
    """Fragt den stündlichen EPEX Spot Preis für den konfigurierten Markt ab."""
    # NEU: Wir fügen den 'market' Parameter zur URL hinzu.
    api_url = f'https://api.awattar.de/v1/marketdata?market={AWATTAR_MARKET}'
    print(f"Rufe Preise für Markt '{AWATTAR_MARKET}' ab von: {api_url}")
    try:
        response = requests.get(api_url, timeout=10)
        response.raise_for_status()
        market_data = response.json()['data']
        now_utc = datetime.now(timezone.utc)
        for price_point in market_data:
            start_time = datetime.fromtimestamp(price_point['start_timestamp'] / 1000, tz=timezone.utc)
            if start_time.hour == now_utc.hour and start_time.date() == now_utc.date():
                return price_point['marketprice'] / 1000
        print(f"WARNUNG: Konnte keinen aktuellen Preis für Markt {AWATTAR_MARKET} finden.")
        return None
    except Exception as e:
        print(f"Fehler bei aWATTar API: {e}")
        return None

def get_solar_forecast():
    # ... (Funktion bleibt unverändert)
    api_url = f"https://api.open-meteo.com/v1/forecast?latitude={LATITUDE}&longitude={LONGITUDE}&hourly=shortwave_radiation&forecast_days=1"
    try:
        response = requests.get(api_url, timeout=10)
        response.raise_for_status()
        data = response.json()
        now_hour = datetime.now(timezone.utc).hour
        return data['hourly']['shortwave_radiation'][now_hour : now_hour + 6]
    except Exception: return None

# --- DER GESICHERTE API-ENDPUNKT ---

@app.get("/entscheidung", response_model=DecisionResponse)
async def get_charging_decision(soc: float, api_key: str = Security(get_api_key)):
    # ... (Der Rest der Funktion bleibt komplett unverändert)
    if not (0.0 <= soc <= 100.0):
        raise HTTPException(status_code=400, detail="SoC muss zwischen 0 und 100 liegen.")
    grid_price = get_epex_spot_price()
    solar_forecast = get_solar_forecast()
    if grid_price is None or solar_forecast is None:
        raise HTTPException(status_code=503, detail="Externe Daten (Strompreis/Wetter) konnten nicht abgerufen werden.")
    decision = "DO_NOTHING"
    reason = "Standard: Keine Aktion nötig."
    next_3h_solar = sum(solar_forecast[0:3])
    if soc < 10:
        decision = "CHARGE_FROM_GRID"
        reason = "Sicherheit: Batterie fast leer, laden um Tiefentladung zu verhindern."
    elif soc > 98:
        decision = "DO_NOTHING"
        reason = "Sicherheit: Batterie fast voll, Ladevorgang gestoppt."
    else:
        if grid_price <= PRICE_THRESHOLD_LOW and soc < 95:
            decision = "CHARGE_FROM_GRID"
            reason = f"Gelegenheit: Netzpreis ist extrem niedrig ({grid_price:.4f} EUR/kWh)."
        elif soc < 80 and next_3h_solar > SOLAR_THRESHOLD_HIGH:
            decision = "WAIT_FOR_SOLAR"
            reason = f"Strategie: Es wird bald genug Solarstrom erwartet (Index: {next_3h_solar})."
        elif grid_price >= PRICE_THRESHOLD_HIGH and soc > 20:
            decision = "DISCHARGE_TO_HOUSE"
            reason = f"Kosten sparen: Netzpreis ist hoch ({grid_price:.4f} EUR/kWh), Batterie wird genutzt."
    conn = None
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO decisions (timestamp_utc, grid_price, solar_forecast_w_m2, input_soc, decision_action, decision_reason)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (datetime.now(timezone.utc), grid_price, str(solar_forecast), soc, decision, reason)
        )
        conn.commit()
        cursor.close()
    except Exception as e:
        print(f"Fehler beim Schreiben in die Datenbank: {e}")
    finally:
        if conn:
            conn.close()
    return {
        "timestamp_utc": datetime.now(timezone.utc),
        "input_soc_percent": soc,
        "data": { "grid_price_eur_per_kwh": grid_price, "next_6h_solar_radiation_w_per_m2": solar_forecast },
        "decision": { "action": decision, "reason": reason }
    }
