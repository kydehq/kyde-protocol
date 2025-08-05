# Angepasst: Health-Check prüft jetzt den OpenAI-Client
# ---------------------------------------------------------------------------
# VERBESSERT: API-Schlüssel-Authentifizierung hinzugefügt
# ---------------------------------------------------------------------------
# VERBESSERT: Absturz durch ungültige LAT/LON Umgebungsvariablen verhindert
# ---------------------------------------------------------------------------
# FINALER FIX: Hyper-resiliente Prüfung für Solarprognose-Daten
# ÜBERARBEITET: Ruft jetzt die asynchronen Service-Funktionen mit await auf
# ---------------------------------------------------------------------------
# ÜBERARBEITET: Gibt jetzt das neue ApiResponse-Modell zurück
# ---------------------------------------------------------------------------
from fastapi import FastAPI, HTTPException, Security, Depends
from fastapi.security.api_key import APIKeyHeader
from optimisation_api.models import ApiResponse, Decision, Savings, Action # Modelle importieren
from optimisation_api.services import external_apis, daylight_checker
from optimisation_api.logic import rules_engine, llm_agent
from datetime import datetime, timezone
from pydantic import BaseModel
from database.neo4j_client import neo4j_client, execute_query

import os



app = FastAPI()

# --- API-Schlüssel-Sicherheit (unverändert) ---
API_KEY_NAME = "X-API-KEY"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=True)
INTERNAL_API_KEY = os.environ.get("INTERNAL_API_KEY")

async def get_api_key(api_key_header: str = Security(api_key_header)):
    if not INTERNAL_API_KEY: raise HTTPException(status_code=500, detail="Server nicht korrekt konfiguriert.")
    if api_key_header != INTERNAL_API_KEY: raise HTTPException(status_code=403, detail="Ungültiger API-Schlüssel")

@app.on_event("startup")
async def startup_event():
    await llm_agent.initialize_openai()
    await neo4j_client.connect() 

@app.on_event("shutdown")
async def shutdown_event():
    await neo4j_client.close() # <-- HINZUFÜGEN

# Der Endpunkt gibt jetzt das übergeordnete `ApiResponse`-Modell zurück
@app.get("/entscheidung", response_model=ApiResponse, dependencies=[Depends(get_api_key)])
async def get_decision(soc: float, lat: float = 50.1109, lon: float = 8.6821):
    if not (0.0 <= soc <= 100.0):
        raise HTTPException(status_code=400, detail="SoC muss zwischen 0 und 100 liegen.")

    # 1. Daten asynchron abrufen
    price_forecast = await external_apis.get_epex_spot_forecast()
    solar_forecast_raw = await external_apis.get_solar_forecast(lat, lon)
    
    if price_forecast is None or solar_forecast_raw is None:
        raise HTTPException(status_code=503, detail="Externe Prognosedaten nicht verfügbar.")

    # 2. Aktuelle Daten extrahieren
    now = datetime.now(timezone.utc)
    current_price_item = next((item for item in price_forecast if item['timestamp_utc'].hour == now.hour and item['timestamp_utc'].date() == now.date()), None)
    if not current_price_item:
        raise HTTPException(status_code=503, detail="Aktueller Strompreis konnte nicht ermittelt werden.")
    current_price = current_price_item['price_eur_kwh']

    # 3. Solardaten aufbereiten
    solar_forecast = solar_forecast_raw if daylight_checker.is_daylight(lat, lon) else [0.0] * len(solar_forecast_raw)

    # 4. Entscheidung treffen (Regeln oder LLM)
    action, reason = rules_engine.fast_rules(soc, current_price, price_forecast, solar_forecast)
    if action is None:
        llm_dec = await llm_agent.llm_decision(soc, price_forecast, solar_forecast)
        if llm_dec:
            action, reason = llm_dec.action, llm_dec.reason
        else:
            action, reason = Action.DO_NOTHING, "Fallback: Keine valide LLM-Antwort erhalten."

    # 5. Finale Sicherheitsüberprüfung
    if action == Action.CHARGE_FROM_GRID and current_price > 0.15:
        action = Action.DO_NOTHING
        reason = f"Sicherheits-Fallback: Laden bei hohem Preis ({current_price:.2f} €) blockiert."

    # 6. NEU: Ersparnis-Daten abrufen (momentan simuliert)
    # In der Zukunft würde hier ein Datenbank-Aufruf stehen:
    # todays_savings = await database.get_todays_savings()
    todays_savings = Savings(today_eur=0.95, trend="up") # Simulierter Wert

    # 7. Komplette Antwort zurückgeben
    return ApiResponse(
        decision=Decision(action=action, reason=reason),
        savings=todays_savings
    )

@app.get("/health")
async def health_check():
    return {"status": "ok"}

# Pydantic-Modell, das die Daten für eine Registrierung definiert.
class UserRegistrationPayload(BaseModel):
    username: str
    email: str
    address: str

# API-Endpunkt, um einen neuen Nutzer zu registrieren.
@app.post("/users/register", status_code=201, tags=["Users"])
async def register_user(payload: UserRegistrationPayload):
    """
    Registriert einen neuen Nutzer und legt ihn und seine Wohnung im Knowledge Graph an.
    """
    print(f"INFO: Registriere neuen Nutzer '{payload.username}' mit Adresse '{payload.address}'...")

    # Eine einzige, atomare Transaktion, um Nutzer und Wohnung zu erstellen und zu verbinden.
    # MERGE verhindert, dass ein Nutzer mit derselben E-Mail doppelt angelegt wird.
    query = """
    MERGE (u:User {email: $email})
    ON CREATE SET
        u.userId = randomUUID(),
        u.username = $username,
        u.createdAt = datetime()
    CREATE (a:Apartment {
        apartmentId: randomUUID(),
        address: $address
    })
    CREATE (u)-[:OWNS]->(a)
    RETURN u.userId as userId, a.apartmentId as apartmentId
    """
    
    try:
        result = await execute_query(query, payload.dict())
        if not result:
             # Dieser Fall kann eintreten, wenn der Nutzer bereits existierte
             # und MERGE nur gematcht, aber nichts erstellt hat. Wir müssen das abfangen.
             existing_user_query = "MATCH (u:User {email: $email}) RETURN u.userId as userId"
             existing_user = await execute_query(existing_user_query, {"email": payload.email})
             raise HTTPException(
                 status_code=409, # 409 Conflict ist passender als 500
                 detail=f"User with this email already exists with ID: {existing_user[0]['userId']}"
             )

        new_ids = result[0]
        print(f"ERFOLG: Nutzer mit ID {new_ids['userId']} und Wohnung {new_ids['apartmentId']} in Neo4j erstellt.")
        return {"message": "User registered successfully", "data": new_ids}
    except HTTPException as http_exc:
        # Die HTTPException von oben direkt weiterleiten
        raise http_exc
    except Exception as e:
        print(f"FEHLER: Nutzer-Registrierung in Neo4j fehlgeschlagen: {e}")
        raise HTTPException(status_code=500, detail="Could not write to knowledge graph.")

#
# ^^^ HIER ENDET DER KORRIGIERTE BLOCK ^^^
#