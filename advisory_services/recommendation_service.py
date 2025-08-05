# advisory_services/recommendation_service.py
# Importiere deine neue Query-Funktion
from database.neo4j_client import execute_query
# ... andere Imports

async def generate_recommendations_for_user(user_id: str) -> list[dict]:
    """
    Erstellt Empfehlungen basierend auf den Daten im Knowledge Graph.
    """
    print(f"INFO: Starte Erstellung von Empfehlungen für Nutzer {user_id}...")
    
    # --- Schritt 1 & 2: Lade Nutzerdaten und identifiziere Stromfresser aus dem Graphen ---
    # Diese eine Cypher-Query ersetzt mehrere SQL-Abfragen!
    query = """
    MATCH (u:User {userId: $userId})-[:OWNS]->(a:Apartment)-[:CONTAINS]->(d:Device)
    WHERE d.efficiency_class IN ['C', 'D', 'E', 'F', 'G'] OR d.avg_consumption_kwh > 1.0
    RETURN d.type as device_type, d.model as device_model, d.deviceId as device_id
    """
    print("-> Schritt 1+2/5: Finde ineffiziente Geräte im Knowledge Graph...")
    inefficient_devices = await execute_query(query, {"userId": user_id})

    if not inefficient_devices:
        print(f"INFO: Keine ineffizienten Geräte für Nutzer {user_id} gefunden.")
        return []

    recommendations = []
    for device in inefficient_devices:
        print(f"-> Verarbeite ineffizientes Gerät: {device['device_type']} ({device['device_model']})")

        # --- Schritt 3: Passende Ersatz-Hardware finden (deine Logik bleibt gleich) ---
        print("-> Schritt 3/5: Suche effiziente Ersatz-Hardware im Produktkatalog...")
        replacement_product = await product_catalog.find_replacement(device['device_type'])

        # --- Schritt 4: Förderungen und Finanzierung prüfen (deine Logik bleibt gleich) ---
        print("-> Schritt 4/5: Prüfe Förderungen und Finanzierungsoptionen...")
        # Hier könntest du sogar User-Profil-Daten aus dem Graphen holen
        # user_profile = await execute_query("MATCH (u:User {userId: $userId}) RETURN u", {"userId": user_id})
        # subsidy = await subsidy_engine.get_subsidies(replacement_product, user_profile[0]['u'])
        # ...

        # --- Schritt 5: Empfehlung zusammenbauen und mit dem Graphen verknüpfen! ---
        # Dies ist der entscheidende Schritt zum Aufbau von Wissen:
        final_recommendation = {
            "title": f"Tausche deine alte {device['device_type']}!",
            # ... andere Felder
        }

        # Jetzt speichern wir die Empfehlung im Graphen und verbinden sie mit dem Nutzer und dem Gerät
        create_recommendation_query = """
        MATCH (u:User {userId: $userId})
        MATCH (d:Device {deviceId: $deviceId})
        CREATE (r:Recommendation {
            recommendationId: randomUUID(),
            title: $title,
            createdAt: datetime(),
            status: 'new'
        })
        CREATE (u)-[:RECEIVED]->(r)
        CREATE (r)-[:SUGGESTS_REPLACEMENT_FOR]->(d)
        RETURN r.recommendationId as id
        """
        await execute_query(create_recommendation_query, {
            "userId": user_id,
            "deviceId": device['device_id'],
            "title": final_recommendation['title']
        })
        print("-> Schritt 5/5: Empfehlung erstellt und im Knowledge Graph gespeichert.")
        recommendations.append(final_recommendation)
    
    return recommendations