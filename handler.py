import os
import json
import requests
from datetime import datetime, timezone

def get_epex_spot_price():
    """
    Fragt die aktuellen EPEX Spot Day-Ahead Preise für Deutschland/Österreich
    über die kostenlose aWATTar API ab.
    """
    api_url = 'https://api.awattar.de/v1/marketdata'
    try:
        response = requests.get(api_url, timeout=10)
        response.raise_for_status()
        market_data = response.json()['data']
        now_utc = datetime.now(timezone.utc)

        for price_point in market_data:
            start_time = datetime.fromtimestamp(price_point['start_timestamp'] / 1000, tz=timezone.utc)
            end_time = datetime.fromtimestamp(price_point['end_timestamp'] / 1000, tz=timezone.utc)

            if start_time <= now_utc < end_time:
                price_eur_per_kwh = price_point['marketprice'] / 1000
                print(f"Erfolgreich von aWATTar abgerufen. Aktueller Preis: {price_eur_per_kwh:.4f} EUR/kWh")
                return {'price_eur_per_kwh': price_eur_per_kwh}

        print("Konnte keinen gültigen Preis für die aktuelle Stunde finden.")
        return None
    except Exception as e:
        print(f"Fehler bei der Anfrage an die aWATTar API: {e}")
        return None

def main():
    """
    Hauptfunktion, die den gesamten Prozess steuert.
    """
    print("Starte stündlichen Preis-Check...")

    # --- 1. Konfiguration aus Umgebungsvariablen lesen ---
    # Diese werden wir später in Railway eintragen
    # tuya_client_id = os.environ.get('TUYA_CLIENT_ID')
    # tuya_client_secret = os.environ.get('TUYA_CLIENT_SECRET')
    # device_id = os.environ.get('DEVICE_ID')

    # if not all([tuya_client_id, tuya_client_secret, device_id]):
    #     print("Fehler: Nicht alle TUYA-Umgebungsvariablen sind gesetzt. Abbruch.")
    #     return

    # print("Tuya-Konfiguration erfolgreich geladen.")

    # --- 2. Aktuellen Strompreis abfragen ---
    current_price_info = get_epex_spot_price()

    if not current_price_info:
        print("Konnte Strompreis nicht abrufen. Abbruch.")
        return

    price = current_price_info.get('price_eur_per_kwh')

    # --- 3. Zukünftige Logik ---
    # Hier kommt deine Logik rein, um basierend auf dem Preis
    # eine Entscheidung zu treffen und die Tuya-API aufzurufen.
    #
    # Beispiel:
    # if price < 0.05:
    #     print("Preis ist sehr niedrig. Sende Lade-Befehl an Tuya...")
    #     # call_tuya_api(device_id, "charge")
    # else:
    #     print("Preis ist normal. Nichts zu tun.")

    print("Preis-Check erfolgreich beendet.")


if __name__ == "__main__":
    main()