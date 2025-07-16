# Angepasst: Health-Check prüft jetzt den OpenAI-Client
# ---------------------------------------------------------------------------
from fastapi import FastAPI, HTTPException
from optimisation_api.models import Decision, Action
from optimisation_api.services import external_apis, daylight_checker
from optimisation_api.logic import rules_engine, llm_agent
from datetime import datetime, timezone
import os

app = FastAPI()

@app.on_event("startup")
async def startup_event():
    """
    Beim Start der API wird der LLM-Client proaktiv initialisiert.
    """
    llm_agent.initialize_openai()

@app.get("/entscheidung", response_model=Decision)
async def get_decision(soc: float):
    if not (0.0 <= soc <= 100.0):
        raise HTTPException(status_code=400, detail="State of Charge (soc) muss zwischen 0 und 100 liegen.")

    # 1. Daten von externen APIs abrufen
    price_forecast = external_apis.get_epex_spot_forecast()
    solar_forecast_raw = external_apis.get_solar_forecast()
    
    if not price_forecast or not solar_forecast_raw:
        raise HTTPException(status_code=503, detail="Externe Prognosedaten sind aktuell nicht verfügbar.")

    # 2. Aktuelle Daten extrahieren
    now = datetime.now(timezone.utc)
    current_price_item = next((item for item in price_forecast if item['timestamp_utc'].hour == now.hour and item['timestamp_utc'].date() == now.date()), None)
    
    if not current_price_item:
        raise HTTPException(status_code=503, detail="Aktueller Strompreis konnte nicht ermittelt werden.")
    current_price = current_price_item['price_eur_kwh']

    # 3. Solardaten aufbereiten (auf 0 setzen, wenn keine Sonne scheint)
    lat = float(os.environ.get("LATITUDE", "50.1109"))
    lon = float(os.environ.get("LONGITUDE", "8.6821"))
    solar_forecast = solar_forecast_raw if daylight_checker.is_daylight(lat, lon) else [0.0] * len(solar_forecast_raw)

    # 4. Schnelle, regelbasierte Entscheidung versuchen
    action, reason = rules_engine.fast_rules(soc, current_price, price_forecast, solar_forecast)

    # 5. Wenn keine Regel zutrifft, den LLM-Agent fragen
    if action is None:
        print("INFO: Keine schnelle Regel hat zugetroffen, frage LLM-Agent...")
        llm_dec = await llm_agent.llm_decision(soc, price_forecast, solar_forecast)
        if llm_dec:
            action, reason = llm_dec.action, llm_dec.reason
        else:
            # Fallback, falls der LLM fehlschlägt
            action, reason = Action.DO_NOTHING, "Fallback: Keine valide LLM-Antwort erhalten."

    # 6. Finale Sicherheitsüberprüfung
    if action == Action.CHARGE_FROM_GRID and current_price > 0.15:
        action = Action.DO_NOTHING
        reason = f"Sicherheits-Fallback: Laden vom Netz bei hohem Preis ({current_price:.2f} €) blockiert."

    return Decision(action=action, reason=reason)

@app.get("/health")
async def health_check():
    """
    Ein einfacher Endpunkt, um den Status des Dienstes und die OpenAI-Verbindung zu prüfen.
    """
    return {
        "status": "ok", 
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "openai_client_available": llm_agent.openai_client is not None
    }
