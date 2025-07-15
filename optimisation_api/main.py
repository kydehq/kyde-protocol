# ---------------------------------------------------------------------------
# DATEI 5: optimisation_api/main.py
# ---------------------------------------------------------------------------
# Das ist der Kern unserer API. Sie importiert die Logik und die Services
# und stellt sie über Endpunkte bereit.

from fastapi import FastAPI, HTTPException
from optimisation_api.models import Decision, Action
from optimisation_api.services import external_apis
from optimisation_api.logic import rules_engine, llm_agent

app = FastAPI()

@app.get("/entscheidung", response_model=Decision)
async def get_decision(soc: float):
    if not (0.0 <= soc <= 100.0):
        raise HTTPException(status_code=400, detail="SoC muss 0–100 sein.")

    grid_price = external_apis.get_epex_spot_price()
    solar = external_apis.get_solar_forecast()
    if grid_price is None or solar is None:
        raise HTTPException(status_code=503, detail="Externe Daten nicht verfügbar.")

    # 1. Deterministische Kurz-Regeln
    action, reason = rules_engine.fast_rules(soc, grid_price, solar)

    # 2. LLM Fallback
    if action is None:
        llm_dec = await llm_agent.llm_decision(soc, grid_price, solar)
        if llm_dec:
            action, reason = llm_dec.action, llm_dec.reason
        else:
            # Wenn auch LLM fehlschlägt, sichere Standardaktion
            action, reason = Action.DO_NOTHING, "Fallback: Keine valide LLM-Antwort."

    # 3. Finaler Sicherheitscheck
    if action == Action.CHARGE_FROM_GRID and grid_price > 0.30:
        action = Action.DO_NOTHING
        reason = f"Sicherheits-Fallback: Laden bei {grid_price:.2f} € blockiert."

    return Decision(action=action, reason=reason)

@app.get("/health")
async def health():
    return {"status": "ok", "gemini_available": llm_agent.gemini_model is not None}
