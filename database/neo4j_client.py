# /app/database/neo4j_client.py

import os
from neo4j import AsyncGraphDatabase, AsyncDriver

class Neo4jClient:
    """
    Ein Wrapper für den Neo4j-Treiber, um die Verbindung zu verwalten.
    """
    def __init__(self):
        self._driver: AsyncDriver | None = None

    async def connect(self):
        """Stellt die Verbindung zur Datenbank her."""
        uri = os.getenv("NEO4J_URI")
        user = os.getenv("NEO4J_USERNAME")
        password = os.getenv("NEO4J_PASSWORD")
        if not all([uri, user, password]):
            print("WARNUNG: Neo4j-Verbindungsdaten nicht vollständig. Neo4j-Client wird nicht initialisiert.")
            return
        
        try:
            self._driver = AsyncGraphDatabase.driver(uri, auth=(user, password))
            await self._driver.verify_connectivity()
            print("INFO: Neo4j-Client erfolgreich verbunden und Konnektivität geprüft.")
        except Exception as e:
            print(f"FATAL: Neo4j-Verbindung fehlgeschlagen: {e}")
            self._driver = None # Sicherstellen, dass der Treiber im Fehlerfall None ist

    async def close(self):
        """Schließt die Verbindung zur Datenbank."""
        if self._driver:
            await self._driver.close()
            print("INFO: Neo4j-Verbindung geschlossen.")

    @property
    def driver(self) -> AsyncDriver:
        if not self._driver:
            # Dieser Fehler sollte die App stoppen, da die DB-Verbindung kritisch ist.
            raise Exception("Neo4j-Treiber nicht initialisiert. 'connect' muss zuerst aufgerufen werden oder ist fehlgeschlagen.")
        return self._driver

# Globale Instanz, die in der gesamten App wiederverwendet wird.
neo4j_client = Neo4jClient()


# WICHTIG: Diese Funktion steht AUßERHALB der Klasse.
async def execute_query(query: str, parameters: dict | None = None, **kwargs):
    """
    Führt eine Cypher-Query sicher aus und gibt die Ergebnisse zurück.
    """
    # Ruft die 'driver' property der globalen Instanz auf
    async with neo4j_client.driver.session(database="neo4j", **kwargs) as session:
        result = await session.run(query, parameters)
        # .data() holt alle Records und gibt sie als Liste von Dictionaries zurück
        return await result.data()