# Wir fügen eine Plausibilitätsprüfung für die Solardaten hinzu.

from fastapi import FastAPI, HTTPException
from optimisation_api.models import Decision, Action
from optimisation_api.services import external_apis, daylight_checker
from optimisation_api.logic import rules_engine, llm_agent
from datetime import datetime, timezone

app = FastAPI()

@app.get("/entscheidung", response_model=Decision)
async def get_decision(soc: float):
    if not (0.0 <= soc <= 100.0):
        raise HTTPException(status_code=400, detail="SoC muss 0–100 sein.")

    # 1. Komplette Prognosen abrufen
    price_forecast = external_apis.get_epex_spot_forecast()
    solar_forecast_raw = external_apis.get_solar_forecast()
    
    if not price_forecast or not solar_forecast_raw:
        raise HTTPException(status_code=503, detail="Externe Daten nicht verfügbar.")

    # 2. Aktuellen Preis extrahieren
    now = datetime.now(timezone.utc)
    current_price_item = next((item for item in price_forecast if item['timestamp_utc'].hour == now.hour), None)
    if not current_price_item:
        raise HTTPException(status_code=503, detail="Aktueller Preis konnte nicht ermittelt werden.")
    current_price = current_price_item['price_eur_kwh']

    # 3. Solar-Plausibilitätsprüfung (bleibt wichtig)
    lat = float(os.environ.get("LATITUDE", "50.1109"))
    lon = float(os.environ.get("LONGITUDE", "8.6821"))
    solar = solar_forecast_raw if daylight_checker.is_daylight(lat, lon) else [0.0] * len(solar_forecast_raw)

    # 4. Deterministische Kurz-Regeln mit Kontext
    action, reason = rules_engine.fast_rules(soc, current_price, price_forecast, solar)

    # 5. LLM Fallback mit Kontext
    if action is None:
        print("Keine schnelle Regel hat zugetroffen, frage LLM mit Zukunftsprognose...")
        llm_dec = await llm_agent.llm_decision(soc, price_forecast, solar)
        if llm_dec:
            action, reason = llm_dec.action, llm_dec.reason
        else:
            action, reason = Action.DO_NOTHING, "Fallback: Keine valide LLM-Antwort."

    # 6. Finaler Sicherheitscheck (bleibt wichtig)
    if action == Action.CHARGE_FROM_GRID and current_price > 0.30:
        action = Action.DO_NOTHING
        reason = f"Sicherheits-Fallback: Laden bei {current_price:.2f} € blockiert."

    return Decision(action=action, reason=reason)


@app.get("/health")
async def health():
    return {"status": "ok", "gemini_available": llm_agent.gemini_model is not None}
