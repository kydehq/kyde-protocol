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
        
    sorted_hours = sorted(future_prices, key=lambda x: x['price_eur_kwh'])
    return [item['timestamp_utc'] for item in sorted_hours[:num_hours]]

def fast_rules(soc: float, current_price: float, price_forecast: list[dict], solar: list[float]) -> tuple[Action | None, str | None]:
    """Smartere Heuristiken, die den Preis-Kontext nutzen."""
    now = datetime.now(timezone.utc)
    
    # Regel 1: Ist jetzt eine der 3 günstigsten Stunden der nächsten 12h und der Preis ist niedrig?
    cheapest_night_hours = find_cheapest_hours(price_forecast, 3)
    if cheapest_night_hours and now.hour in [ts.hour for ts in cheapest_night_hours]:
        if soc < 95 and current_price < 0.15:
            return Action.CHARGE_FROM_GRID, f"Regel: Günstigste Stunde (Preis: {current_price:.2f}€) wird zum Laden genutzt."

    # Regel 2: Hohe Solarprognose und Batterie nicht voll? Warten.
    now_hour = datetime.now(timezone.utc).hour
    cloud = data["cloud_cover"][now_hour : now_hour + 6]
    if max(solar, default=0) > 300 and soc < 85:
        return Action.WAIT_FOR_SOLAR, f"Regel: Hohe Solarprognose ({max(solar):.0f} W/m²) & Batterie <85%."

    # Regel 3: Hoher Preis und Batterie hat genug Ladung? Entladen.
    if soc > 50 and current_price > 0.28:
        return Action.DISCHARGE_TO_HOUSE, f"Regel: Hoher Preis ({current_price:.2f}€) & SoC >50%."
        
    return None, None
