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