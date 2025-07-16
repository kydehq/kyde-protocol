# connectors/base.py
from abc import ABC, abstractmethod

class BatteryConnector(ABC):
    @abstractmethod
    async def get_soc_percent(self) -> float:
        """Gibt den aktuellen Ladestand der Batterie in Prozent zurück."""
        pass

    @abstractmethod
    async def set_charge_mode(self, mode: str):
        """Setzt den Modus der Batterie, z.B. 'charge', 'discharge', 'idle'."""
        pass

    # ... weitere notwendige Funktionen