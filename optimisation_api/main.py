# Wir fügen eine Plausibilitätsprüfung für die Solardaten hinzu.

from fastapi import FastAPI, HTTPException
from optimisation_api.models import Decision, Action
from optimisation_api.services import external_apis
from optimisation_api.logic import rules_engine, llm_agent
from datetime import datetime, timezone
# NEU: Wir importieren die neue Funktion zur Überprüfung der Tageszeit
from optimisation_api.services.daylight_checker import is_daylight

app = FastAPI()

@app.get("/entscheidung", response_model=Decision)
async def get_decision(soc: float):
    if not (0.0 <= soc <= 100.0):
        raise HTTPException(status_code=400, detail="SoC muss 0–100 sein.")

    # 1. Externe Daten abrufen
    grid_price = external_apis.get_epex_spot_price()
    solar_forecast_raw = external_apis.get_solar_forecast()
    
    if grid_price is None or solar_forecast_raw is None:
        raise HTTPException(status_code=503, detail="Externe Daten nicht verfügbar.")

    # 2. NEU: Plausibilitätsprüfung (Sanity Check)
    # Wir holen uns die GPS-Koordinaten aus der Konfiguration
    lat = float(external_apis.get_config("LATITUDE", "50.1109"))
    lon = float(external_apis.get_config("LONGITUDE", "8.6821"))

    if is_daylight(lat, lon):
        solar = solar_forecast_raw
        daylight_status = "Tag"
    else:
        # Wenn es Nacht ist, überschreiben wir die API-Daten.
        solar = [0.0] * len(solar_forecast_raw)
        daylight_status = "Nacht (Solarprognose ignoriert)"
    
    print(f"Tageszeit-Status: {daylight_status}")


    # 3. Deterministische Kurz-Regeln
    action, reason = rules_engine.fast_rules(soc, grid_price, solar)

    # 4. LLM Fallback
    if action is None:
        print("Keine schnelle Regel hat zugetroffen, frage LLM...")
        llm_dec = await llm_agent.llm_decision(soc, grid_price, solar)
        if llm_dec:
            action, reason = llm_dec.action, llm_dec.reason
        else:
            action, reason = Action.DO_NOTHING, "Fallback: Keine valide LLM-Antwort."

    # 5. Finaler Sicherheitscheck
    if action == Action.CHARGE_FROM_GRID and grid_price > 0.30:
        action = Action.DO_NOTHING
        reason = f"Sicherheits-Fallback: Laden bei {grid_price:.2f} € blockiert."

    return Decision(action=action, reason=reason)

@app.get("/health")
async def health():
    return {"status": "ok", "gemini_available": llm_agent.gemini_model is not None}
