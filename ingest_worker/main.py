# ---------------------------------------------------------------------------
# DATEI 6: ingest_worker/main.py (Platzhalter)
# ---------------------------------------------------------------------------
# Dies wäre ein separater Dienst, der als Cron-Job läuft.
# Seine einzige Aufgabe: Daten vom Shelly holen und in die Datenbank schreiben.

from database.neo4j_client import execute_query

async def create_or_update_device_in_graph(user_id, device_data):
    """
    Erstellt einen Geräteknoten in Neo4j und verbindet ihn mit dem Nutzer/Apartment.
    MERGE sorgt dafür, dass ein Gerät nicht doppelt angelegt wird.
    """
    query = """
    MATCH (u:User {userId: $userId})-[:OWNS]->(a:Apartment)
    MERGE (d:Device {deviceId: $deviceId})
    ON CREATE SET
        d.type = $type,
        d.model = $model,
        d.firstSeen = datetime()
    ON MATCH SET
        d.lastSeen = datetime()
    MERGE (a)-[:CONTAINS]->(d)
    """
    await execute_query(query, {
        "userId": user_id,
        "deviceId": device_data['id'],
        "type": device_data['type'],
        "model": device_data['model_name']
    })

import time
# from collectors import shelly_collector
# from database import timescaledb_writer

def main():
    print("Starte Ingest-Worker...")
    while True:
        # house_data = shelly_collector.get_data()
        # if house_data:
        #     timescaledb_writer.save(house_data)
        print("Daten gesammelt. Schlafe für 60 Sekunden.")
        time.sleep(60)

if __name__ == "__main__":
    main()



    # Fester Vergleichspreis aus der Umgebung holen
FIXED_PRICE = float(os.environ.get("DEFAULT_GRID_PRICE_EUR_KWH", "0.32"))

def calculate_and_save_savings():
    # 1. Tatsächliche Verbrauchsdaten der letzten Stunde vom Shelly holen
    last_hour_data = shelly.get_data() # z.B. { consumption: 1.5, from_solar: 1.0, from_battery: 0.5 }

    # 2. Kosten OHNE System berechnen
    cost_without_system = last_hour_data.consumption * FIXED_PRICE # 1.5 kWh * 0.32€

    # 3. Kosten MIT System berechnen
    # (Annahme: Solar ist gratis, Batterie wurde für 0.12€ geladen)
    cost_with_system = (0 * last_hour_data.from_solar) + (0.12 * last_hour_data.from_battery)

    # 4. Ersparnis dieser Stunde berechnen und zur Tagesersparnis addieren
    hourly_saving = cost_without_system - cost_with_system
    database.add_to_todays_savings(hourly_saving)