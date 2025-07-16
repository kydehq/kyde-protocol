# ÜBERARBEITET: Nutzt jetzt openai.AsyncOpenAI
# ---------------------------------------------------------------------------
import os
import time
import json
from datetime import datetime, timezone
import openai
from pydantic import ValidationError
from optimisation_api.models import Decision, Action

# --- Globale Variablen für den "Lazy Load" des asynchronen OpenAI-Clients ---
# WICHTIG: AsyncOpenAI verwenden!
openai_client: openai.AsyncOpenAI | None = None
openai_initialized = False

SYSTEM_PROMPT = """
Du bist ein Experte für Energie-Management von Heimbatterien. Deine Ziele sind:
- Stromkosten durch intelligentes Laden und Entladen minimieren.
- Versorgungssicherheit des Hauses gewährleisten.
- Die Batterie schonen, indem ein Puffer von mindestens 20% SoC (State of Charge) angestrebt wird, wann immer möglich.

Du kannst aus den folgenden Aktionen wählen:
- "CHARGE_FROM_GRID": Lade die Batterie aus dem Netz (nur bei sehr günstigen oder negativen Preisen).
- "DISCHARGE_TO_HOUSE": Entlade die Batterie, um den Hausverbrauch zu decken (nur bei hohen Preisen, um Netzeinkauf zu vermeiden).
- "WAIT_FOR_SOLAR": Tue nichts und warte auf die erwartete Sonneneinstrahlung zum Laden.
- "DO_NOTHING": Die Batterie weder laden noch entladen. Dies ist die Standardaktion, wenn keine andere Aktion sinnvoll ist.

Deine Antwort MUSS IMMER ein valides JSON-Objekt sein, das genau diesem Schema folgt:
{"action": "AKTION", "reason": "Eine kurze, klare Begründung für deine Entscheidung."}
"""

MAX_LLM_RUNTIME = 3.0

# Die Funktion ist jetzt auch async
async def initialize_openai():
    """
    Initialisiert den asynchronen OpenAI-Client sicher.
    """
    global openai_client, openai_initialized
    if openai_initialized:
        return

    print("--- INFO: Initialisiere Async-OpenAI-Client... ---")
    try:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("FATAL: OPENAI_API_KEY Umgebungsvariable nicht gefunden oder leer.")
        
        # AsyncOpenAI-Client erstellen
        openai_client = openai.AsyncOpenAI(api_key=api_key)
        
        # Verbindung mit einem asynchronen Aufruf testen
        await openai_client.models.list()
        print(f"--- ERFOLG: Async-OpenAI-Client erfolgreich initialisiert und verbunden. ---")

    except Exception as e:
        print(f"--- FATAL: Async-OpenAI-Initialisierung fehlgeschlagen. Der LLM-Agent wird nicht verfügbar sein. ---")
        print(f"Fehlertyp: {type(e).__name__}")
        print(f"Fehlermeldung: {e}")
        openai_client = None
    finally:
        openai_initialized = True


async def llm_decision(soc: float, price_forecast: list[dict], solar: list[float]) -> Decision | None:
    """
    Trifft eine Entscheidung mithilfe des asynchronen OpenAI-Modells.
    """
    # Stelle sicher, dass der Client initialisiert ist.
    await initialize_openai()

    if not openai_client:
        print("WARNUNG: LLM-Entscheidung übersprungen, da OpenAI-Client nicht verfügbar ist.")
        return None

    # ... (Prompt-Vorbereitung bleibt gleich)
    future_prices = [item for item in price_forecast if item['timestamp_utc'] > datetime.now(timezone.utc)]
    price_str = "\\n".join([f"- {item['timestamp_utc'].strftime('%H:%M')}: {item['price_eur_kwh']:.4f} €" for item in future_prices[:8]])
    now = datetime.now(timezone.utc)
    current_price_item = next((item for item in price_forecast if item['timestamp_utc'].hour == now.hour and item['timestamp_utc'].date() == now.date()), None)
    current_price = current_price_item['price_eur_kwh'] if current_price_item else "N/A"
    user_prompt = (
        f"AKTUELLE SITUATION:\n- Batteriestand (SoC): {soc:.1f}%\n- Aktueller Netzpreis: {current_price:.4f} €/kWh\n\n"
        f"PROGNOSEN:\n- Preisprognose (kommende Stunden):\n{price_str}\n- Solarprognose (kommende 6h in Watt pro m²): {solar}\n\n"
        f"AUFGABE: Analysiere die Daten und entscheide, welche Aktion **jetzt sofort** die wirtschaftlich und technisch sinnvollste ist. Gib deine Antwort ausschließlich im geforderten JSON-Format zurück."
    )
    
    try:
        print("INFO: Sende Anfrage an OpenAI API (async)...")
        start_time = time.monotonic()

        # Der asynchrone API-Aufruf
        response = await openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
            timeout=MAX_LLM_RUNTIME,
        )
        
        duration = time.monotonic() - start_time
        print(f"INFO: Antwort von OpenAI in {duration:.2f}s erhalten.")
        
        response_json = json.loads(response.choices[0].message.content)
        decision = Decision.parse_obj(response_json)
        print(f"INFO: Valide LLM-Entscheidung erhalten: {decision.action} -> {decision.reason}")
        return decision

    except openai.APITimeoutError:
        print(f"FEHLER: OpenAI API-Anfrage hat das Timeout von {MAX_LLM_RUNTIME}s überschritten.")
        return None
    except Exception as e:
        print(f"FEHLER: Ein unerwarteter Fehler im LLM-Agent ist aufgetreten: {e}")
        return None

