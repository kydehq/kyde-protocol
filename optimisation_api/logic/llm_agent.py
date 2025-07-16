# STARK ÜBERARBEITET: Umbau von Gemini auf OpenAI
# ---------------------------------------------------------------------------
import os
import time
import json
from datetime import datetime, timezone
import openai
from pydantic import ValidationError
from optimisation_api.models import Decision, Action

# --- Globale Variablen für den "Lazy Load" des OpenAI-Clients ---
openai_client = None
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
Beispiel: {"action": "CHARGE_FROM_GRID", "reason": "Nutze die sehr günstigen Nachtpreise, um die Batterie für den Tag vorzubereiten."}
"""

# Timeout für die API-Anfrage in Sekunden
MAX_LLM_RUNTIME = 3.0

def initialize_openai():
    """
    Initialisiert den OpenAI-Client sicher.
    Wird nur beim ersten Bedarf aufgerufen ("lazy initialization").
    """
    global openai_client, openai_initialized
    if openai_initialized:
        return

    print("--- INFO: Initialisiere OpenAI-Client... ---")
    try:
        # Lese den API-Schlüssel aus den Umgebungsvariablen.
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("FATAL: OPENAI_API_KEY Umgebungsvariable nicht gefunden oder leer.")
        
        # Erstelle den Client
        global openai_client
        openai_client = openai.OpenAI(api_key=api_key)
        
        # Teste die Verbindung mit einem einfachen Aufruf (optional, aber empfohlen)
        openai_client.models.list()
        print(f"--- ERFOLG: OpenAI-Client erfolgreich initialisiert und verbunden. ---")

    except Exception as e:
        print(f"--- FATAL: OpenAI-Initialisierung fehlgeschlagen. Der LLM-Agent wird nicht verfügbar sein. ---")
        print(f"Fehlertyp: {type(e).__name__}")
        print(f"Fehlermeldung: {e}")
        openai_client = None
    finally:
        # Markiere die Initialisierung als abgeschlossen, um Wiederholungen zu vermeiden.
        openai_initialized = True


async def llm_decision(soc: float, price_forecast: list[dict], solar: list[float]) -> Decision | None:
    """
    Trifft eine Entscheidung mithilfe des OpenAI-Modells.
    """
    # Stelle sicher, dass der Client initialisiert ist.
    initialize_openai()

    if not openai_client:
        print("WARNUNG: LLM-Entscheidung übersprungen, da OpenAI-Client nicht verfügbar ist.")
        return None

    # Bereite die Daten für den Prompt auf
    future_prices = [item for item in price_forecast if item['timestamp_utc'] > datetime.now(timezone.utc)]
    price_str = "\\n".join([f"- {item['timestamp_utc'].strftime('%H:%M')}: {item['price_eur_kwh']:.4f} €" for item in future_prices[:8]])
    
    now = datetime.now(timezone.utc)
    current_price_item = next((item for item in price_forecast if item['timestamp_utc'].hour == now.hour and item['timestamp_utc'].date() == now.date()), None)
    current_price = current_price_item['price_eur_kwh'] if current_price_item else "N/A"

    user_prompt = (
        f"AKTUELLE SITUATION:\n"
        f"- Batteriestand (SoC): {soc:.1f}%\n"
        f"- Aktueller Netzpreis: {current_price:.4f} €/kWh\n\n"
        f"PROGNOSEN:\n"
        f"- Preisprognose (kommende Stunden):\n{price_str}\n"
        f"- Solarprognose (kommende 6h in Watt pro m²): {solar}\n\n"
        f"AUFGABE: Analysiere die Daten und entscheide, welche Aktion **jetzt sofort** die wirtschaftlich und technisch sinnvollste ist. Gib deine Antwort ausschließlich im geforderten JSON-Format zurück."
    )
    
    try:
        print("INFO: Sende Anfrage an OpenAI API...")
        start_time = time.monotonic()

        # Der eigentliche API-Aufruf
        response = await openai_client.chat.completions.create(
            model="gpt-4o", # oder "gpt-3.5-turbo" für eine schnellere/günstigere Alternative
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"}, # Wichtig: Aktiviert den JSON-Modus
            temperature=0.2,
            timeout=MAX_LLM_RUNTIME,
        )
        
        duration = time.monotonic() - start_time
        print(f"INFO: Antwort von OpenAI in {duration:.2f}s erhalten.")

        # Antwort extrahieren und parsen
        response_text = response.choices[0].message.content
        response_json = json.loads(response_text)
        
        # Validierung mit Pydantic
        decision = Decision.parse_obj(response_json)
        print(f"INFO: Valide LLM-Entscheidung erhalten: {decision.action} -> {decision.reason}")
        return decision

    except openai.APITimeoutError:
        print(f"FEHLER: OpenAI API-Anfrage hat das Timeout von {MAX_LLM_RUNTIME}s überschritten.")
        return None
    except (openai.APIError, ValidationError, json.JSONDecodeError) as e:
        print(f"FEHLER: Ein Fehler ist bei der Verarbeitung der LLM-Antwort aufgetreten.")
        print(f"Fehlertyp: {type(e).__name__}")
        print(f"Fehlermeldung: {e}")
        return None
    except Exception as e:
        print(f"FEHLER: Ein unerwarteter Fehler im LLM-Agent ist aufgetreten: {e}")
        return None
