# Wir initialisieren den Gemini-Client jetzt "lazy" und mit verbessertem Fehler-Handling.

import os
import time
import json
from datetime import datetime, timezone
import google.generativeai as genai
from google.generativeai.types import GenerationConfig
from pydantic import ValidationError
from optimisation_api.models import Decision

# --- Globale Variablen für den "Lazy Load" ---
gemini_model = None
gemini_initialized = False

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

def initialize_gemini():
    """
    Diese Funktion initialisiert den Gemini-Client.
    Sie wird nur einmal aufgerufen, wenn sie zum ersten Mal benötigt wird.
    """
    global gemini_model, gemini_initialized
    if gemini_initialized:
        return

    print("--- START: Initialisiere Gemini-Client ---")
    # Wir fangen jetzt BaseException ab, um absolut alles zu erwischen, auch System-Level-Fehler.
    try:
        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            # Dieser Fehler sollte jetzt klar in den Logs erscheinen.
            raise ValueError("FATAL: GOOGLE_API_KEY Umgebungsvariable wurde nicht gefunden oder ist leer.")
        
        print(f"API-Schlüssel gefunden, beginnt mit: {api_key[:4]}...")
        
        genai.configure(api_key=api_key)
        json_cfg = GenerationConfig(response_mime_type="application/json")
        gemini_model = genai.GenerativeModel("gemini-1.5-flash", generation_config=json_cfg)
        print("--- ERFOLG: Gemini-Client erfolgreich initialisiert. ---")
    except BaseException as exc: # Fängt absolut alles ab
        print(f"--- FATAL: Gemini-Initialisierung fehlgeschlagen. Der Prozess stürzt möglicherweise ab. ---")
        print(f"Fehlertyp: {type(exc).__name__}")
        print(f"Fehlermeldung: {exc}")
        # Wir setzen das Modell auf None, damit der Rest der App nicht abstürzt
        gemini_model = None
    finally:
        # Wir markieren die Initialisierung als abgeschlossen, um wiederholte Versuche zu vermeiden.
        gemini_initialized = True
        print("--- ENDE: Gemini-Initialisierungsversuch abgeschlossen. ---")


async def llm_decision(soc: float, price_forecast: list[dict], solar: list[float]) -> Decision | None:
    # Stelle sicher, dass der Client initialisiert ist, bevor wir ihn nutzen.
    initialize_gemini()

    if not gemini_model:
        print("LLM-Entscheidung übersprungen, da Gemini-Client nicht verfügbar ist.")
        return None

    # ... (Der Rest der Funktion bleibt exakt gleich)
    future_prices = [item for item in price_forecast if item['timestamp_utc'] > datetime.now(timezone.utc)]
    price_str = "\\n".join([f"- {item['timestamp_utc'].strftime('%H:%M')}: {item['price_eur_kwh']:.4f} €" for item in future_prices[:8]])
    
    now = datetime.now(timezone.utc)
    current_price_item = next((item for item in price_forecast if item['timestamp_utc'].hour == now.hour and item['timestamp_utc'].date() == now.date()), None)
    current_price = current_price_item['price_eur_kwh'] if current_price_item else "N/A"

    user_prompt = (
        f"SITUATION:\\n"
        f"- Aktueller Batteriestand (SoC): {soc:.1f}%\\n"
        f"- Aktueller Netzpreis: {current_price:.4f} €/kWh\\n"
        f"PROGNOSEN:\\n"
        f"- Preisprognose (nächste Stunden):\\n{price_str}\\n"
        f"- Solarprognose (nächste 6h in W/m²): {solar}\\n\\n"
        f"AUFGABE: Was ist die **jetzt** zu treffende, optimale Aktion?"
    )
    try:
        print("Sende Anfrage an Gemini...")
        start = time.monotonic()
        resp = await gemini_model.generate_content_async([SYSTEM_PROMPT, user_prompt])
        if time.monotonic() - start > MAX_LLM_RUNTIME:
            raise TimeoutError("LLM timeout")
        
        cleaned_text = resp.text.strip().replace("```json", "").replace("```", "").strip()
        dec = Decision.parse_obj(json.loads(cleaned_text))
        print("Valide JSON-Antwort von Gemini erhalten.")
        return dec
    except Exception as exc:
        print(f"LLM error während der Ausführung: {exc}")
        return None