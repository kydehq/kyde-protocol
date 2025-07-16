# ---------------------------------------------------------------------------
# DATEI 1: optimisation_api/models.py
# ---------------------------------------------------------------------------
# Hier definieren wir unsere Datenstrukturen. Das ist die "Sprache",
# die alle unsere Dienste sprechen werden.

from enum import Enum
from pydantic import BaseModel

class Action(str, Enum):
    CHARGE_FROM_GRID = "CHARGE_FROM_GRID"
    DISCHARGE_TO_HOUSE = "DISCHARGE_TO_HOUSE"
    WAIT_FOR_SOLAR = "WAIT_FOR_SOLAR"
    DO_NOTHING = "DO_NOTHING"

class Decision(BaseModel):
    action: Action
    reason: str

# Ein Modell für die Ersparnis-Daten
class Savings(BaseModel):
    today_eur: float
    trend: str # 'up', 'down', or 'stable'

# Ein übergeordnetes Antwort-Modell, das alles enthält
class ApiResponse(BaseModel):
    decision: Decision
    savings: Savings
    # Hier könnten später weitere Daten hinzukommen, z.B. Batteriestatus
    # battery_soc: float