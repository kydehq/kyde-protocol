# ---------------------------------------------------------------------------
# DATEI 6: ingest_worker/main.py (Platzhalter)
# ---------------------------------------------------------------------------
# Dies wäre ein separater Dienst, der als Cron-Job läuft.
# Seine einzige Aufgabe: Daten vom Shelly holen und in die Datenbank schreiben.

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