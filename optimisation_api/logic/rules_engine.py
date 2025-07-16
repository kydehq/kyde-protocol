# ---------------------------------------------------------------------------
# DATEI 3: optimisation_api/logic/rules_engine.py
# ---------------------------------------------------------------------------
# Das ist unser "Brain v1" - die schnellen, deterministischen Regeln.

# Die Regeln basieren nicht mehr auf festen Schwellen, sondern auf dem Preis-Kontext.

# VERBESSERT: Die Begründung für die Solar-Regel ist jetzt klarer.
# ===========================================================================
import os
from optimisation_api.models import Action
from datetime import datetime, timezone

# 1. Lese die Hardware-Grenzen aus den Umgebungsvariablen
BMS_MIN_SOC = float(os.environ.get("BMS_MIN_SOC_PERCENT", "5"))
BMS_MAX_SOC = float(os.environ.get("BMS_MAX_SOC_PERCENT", "99"))

# 2. Definiere die strategischen Puffer, die die KI einhalten soll
STRATEGIC_MIN_SOC = BMS_MIN_SOC + 10  # Ergibt z.B. 15%
STRATEGIC_MAX_SOC = BMS_MAX_SOC - 5   # Ergibt z.B. 94%

def fast_rules(soc: float, current_price: float, price_forecast: list[dict], solar: list[float]) -> tuple[Action | None, str | None]:
    """Smartere Heuristiken, die jetzt die strategischen Puffer nutzen."""
    
    # 3. NEUE Top-Priorität-Sicherheitsregel
    if soc < STRATEGIC_MIN_SOC:
        return Action.CHARGE_FROM_GRID, f"Regel: Strategischer Puffer ({STRATEGIC_MIN_SOC}%) unterschritten. Sicherheitsladung wird eingeleitet."

    # 4. Bestehende Regeln anpassen, um die oberen Puffer zu respektieren
    # Regel zum Warten auf Solar: Gilt nur, wenn wir unter dem strategischen Maximum sind.
    max_solar_forecast = max(solar, default=0)
    if max_solar_forecast > 300 and soc < STRATEGIC_MAX_SOC:
        # VERBESSERTE BEGRÜNDUNG: Zeigt jetzt den konkreten Wert der Solarprognose an.
        return Action.WAIT_FOR_SOLAR, f"Regel: Solarprognose ({max_solar_forecast:.0f} W/m²) ist hoch & Batterie <{STRATEGIC_MAX_SOC}%."

    # Regel zum Entladen bei hohen Preisen: Gilt nur, wenn wir über dem strategischen Minimum sind.
    if soc > STRATEGIC_MIN_SOC and current_price > 0.28:
        return Action.DISCHARGE_TO_HOUSE, f"Regel: Hoher Preis (>28 ct) & SoC >{STRATEGIC_MIN_SOC}%."
        
    # Regel zum Laden bei günstigen Preisen: Respektiert ebenfalls die Obergrenze.
    cheapest_night_hours = find_cheapest_hours(price_forecast, 3)
    if cheapest_night_hours and datetime.now(timezone.utc).hour in [ts.hour for ts in cheapest_night_hours]:
        if soc < STRATEGIC_MAX_SOC and current_price < 0.15:
            return Action.CHARGE_FROM_GRID, f"Regel: Günstigste Stunde wird zum Laden bis {STRATEGIC_MAX_SOC}% genutzt."

    return None, None

def find_cheapest_hours(price_forecast: list[dict], num_hours: int) -> list[datetime]:
    """Findet die 'num_hours' günstigsten Stunden in der Zukunft."""
    now = datetime.now(timezone.utc)
    future_prices = [item for item in price_forecast if item['timestamp_utc'] > now]
    if not future_prices:
        return []
    sorted_hours = sorted(future_prices, key=lambda x: x['price_eur_kwh'])
    return [item['timestamp_utc'] for item in sorted_hours[:num_hours]]
