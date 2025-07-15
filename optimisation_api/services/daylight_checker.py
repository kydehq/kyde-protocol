# Diese Datei enthält die Logik zur Berechnung von Sonnenauf- und -untergang.

from datetime import datetime, timezone
from astral import LocationInfo
from astral.sun import sun

def is_daylight(latitude: float, longitude: float) -> bool:
    """
    Überprüft, ob am gegebenen Ort aktuell Tageslicht herrscht.
    """
    try:
        # Erstelle ein LocationInfo-Objekt
        city = LocationInfo("CustomCity", "CustomRegion", "UTC", latitude, longitude)
        
        # Berechne die Sonnenzeiten für heute
        s = sun(city.observer, date=datetime.now(timezone.utc), tzinfo=timezone.utc)
        
        # Aktuelle Zeit in UTC
        now_utc = datetime.now(timezone.utc)
        
        # Überprüfe, ob die aktuelle Zeit zwischen Sonnenaufgang und Sonnenuntergang liegt
        return s['sunrise'] < now_utc < s['sunset']
    except Exception as e:
        print(f"Fehler bei der Tageslicht-Berechnung: {e}")
        # Im Fehlerfall gehen wir sicherheitshalber von Nacht aus
        return False