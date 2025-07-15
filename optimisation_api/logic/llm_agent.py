# ---------------------------------------------------------------------------
# DATEI 4: optimisation_api/logic/llm_agent.py
# ---------------------------------------------------------------------------
# Das ist unser "Brain v1+" - der intelligente Agent, der Gemini nutzt.

import os
import time
import json
import google.generativeai as genai
from google.generativeai.types import GenerationConfig
from pydantic import ValidationError
from optimisation_api.models import Decision

# --- Initialisierung ---
try:
    genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
    json_cfg = GenerationConfig(response_mime_type="application/json")
    gemini_model = genai.GenerativeModel("gemini-1.5-flash", generation_config=json_cfg)
except Exception as exc:
    print("Gemini init failed:", exc)
    gemini_model = None

SYSTEM_PROMPT = """
Du bist ein Experte für Energie-Management von Heimbatterien. Ziele:
- Stromkosten minimieren
- Versorgungssicherheit gewährleisten
- Batterie schonen (≥20% SoC Puffer)

Aktionen:
- CHARGE_FROM_GRID
- DISCHARGE_TO_HOUSE
- WAIT_FOR_SOLAR
- DO_NOTHING

Gib ausschließlich ein JSON-Objekt im Format {"action":"...", "reason":"..."} zurück.
"""
MAX_LLM_RUNTIME = 2.0  # seconds

async def llm_decision(soc: float, price_forecast: list[dict], solar: list[float]) -> Decision | None:
    if not gemini_model:
        return None

    # Bereite die Prognosen für den Prompt vor
    price_str = "\\n".join([f"- {item['timestamp_utc'].strftime('%H:%M')}: {item['price_eur_kwh']:.4f} €" for item in price_forecast[:8]])
    
    # Finde den aktuellen Preis für den Prompt
    now = datetime.now(timezone.utc)
    current_price_item = next((item for item in price_forecast if item['timestamp_utc'].hour == now.hour), None)
    current_price = current_price_item['price_eur_kwh'] if current_price_item else "N/A"

    user_prompt = (
        f"SITUATION:\\n"
        f"- Aktueller Batteriestand (SoC): {soc:.1f}%\\n"
        f"- Aktueller Netzpreis: {current_price:.4f} €/kWh\\n"
        f"PROGNOSEN:\\n"
        f"- Preisprognose (nächste 8h):\\n{price_str}\\n"
        f"- Solarprognose (nächste 6h in W/m²): {solar}\\n\\n"
        f"AUFGABE: Was ist die **jetzt** zu treffende, optimale Aktion?"
    )
    try:
        start = time.monotonic()
        resp = await gemini_model.generate_content_async([SYSTEM_PROMPT, user_prompt])
        if time.monotonic() - start > MAX_LLM_RUNTIME:
            raise TimeoutError("LLM timeout")
        
        # Sicherstellen, dass der Text sauber ist, bevor er geparst wird.
        cleaned_text = resp.text.strip().replace("```json", "").replace("```", "").strip()
        dec = Decision.parse_obj(json.loads(cleaned_text))
        return dec
    except (ValidationError, json.JSONDecodeError, Exception) as exc:
        print(f"LLM error: {exc}")
        return None
