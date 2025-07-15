# ---------------------------------------------------------------------------
# DATEI 3: optimisation_api/logic/rules_engine.py
# ---------------------------------------------------------------------------
# Das ist unser "Brain v1" - die schnellen, deterministischen Regeln.

from optimisation_api.models import Action

def fast_rules(soc: float, grid_price: float, solar: list[float]) -> tuple[Action | None, str | None]:
    """Simple heuristics that cover majority of cases."""
    if soc < 20 and grid_price < 0.15:
        return Action.CHARGE_FROM_GRID, "Regel: SoC <20% & günstiger Netzpreis (<15 ct)."
    if max(solar) > 350 and soc < 80:
        return Action.WAIT_FOR_SOLAR, "Regel: Hohe Solarprognose & Batterie <80%."
    if soc > 60 and grid_price > 0.28:
        return Action.DISCHARGE_TO_HOUSE, "Regel: Hoher Preis (>28 ct) & SoC >60%."
    return None, None