# ---------------------------------------------------------------------------
# DATEI 3: optimisation_api/logic/rules_engine.py
# ---------------------------------------------------------------------------
# Das ist unser "Brain v1" - die schnellen, deterministischen Regeln.

# Die Regeln basieren nicht mehr auf festen Schwellen, sondern auf dem Preis-Kontext.

from optimisation_api.models import Action
from datetime import datetime, timezone

def find_cheapest_hours(price_forecast: list[dict], num_hours: int) -> list[datetime]:
    """Findet die 'num_hours' günstigsten Stunden in der Zukunft."""
    now = datetime.now(timezone.utc)
    future_prices = [item for item in price_forecast if item['timestamp_utc'] > now]
    
    if not future_prices:
        return []
        
    # Sortiere die zukünftigen Stunden nach Preis
    sorted_hours = sorted(future_prices, key=lambda x: x['price_eur_kwh'])
    
    # Gib die Zeitstempel der günstigsten Stunden zurück
    return [item['timestamp_utc'] for item in sorted_hours[:num_hours]]

def fast_rules(soc: float, current_price: float, price_forecast: list[dict], solar: list[float]) -> tuple[Action | None, str | None]:
    """Smartere Heuristiken, die den Preis-Kontext nutzen."""
    now = datetime.now(timezone.utc)
    
    # Regel 1: Ist jetzt eine der 3 günstigsten Stunden der nächsten 12h? Wenn ja, laden!
    cheapest_night_hours = find_cheapest_hours(price_forecast, 3)
    if cheapest_night_hours and now.hour in [ts.hour for ts in cheapest_night_hours]:
        if soc < 95:
            return Action.CHARGE_FROM_GRID, "Regel: Aktuelle Stunde ist eine der günstigsten Lade-Gelegenheiten."

    # Regel 2: Hohe Solarprognose? Warten. (Bleibt gleich)
    if max(solar) > 350 and soc < 80:
        return Action.WAIT_FOR_SOLAR, "Regel: Hohe Solarprognose & Batterie <80%."

    # Regel 3: Hoher Preis? Entladen. (Bleibt gleich, aber der Schwellenwert könnte dynamisch sein)
    if soc > 60 and current_price > 0.28:
        return Action.DISCHARGE_TO_HOUSE, "Regel: Hoher Preis (>28 ct) & SoC >60%."
        
    return None, None