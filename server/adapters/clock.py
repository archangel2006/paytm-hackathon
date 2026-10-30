from datetime import datetime, timezone, timedelta
from typing import Optional

class Clock:
    def __init__(self, offset_seconds: float = 0.0):
        self._offset_seconds: float = offset_seconds

    def now(self) -> datetime:
        """Returns the current simulated time (UTC timezone-aware)."""
        return datetime.now(timezone.utc) + timedelta(seconds=self._offset_seconds)

    def advance(self, hours: float = 0.0, seconds: float = 0.0) -> datetime:
        """Advances the simulated clock by hours/seconds."""
        self._offset_seconds += (hours * 3600.0) + seconds
        return self.now()

    def reset(self) -> datetime:
        """Resets the clock offset back to zero."""
        self._offset_seconds = 0.0
        return self.now()

    @property
    def offset_seconds(self) -> float:
        return self._offset_seconds

    @offset_seconds.setter
    def offset_seconds(self, value: float) -> None:
        self._offset_seconds = float(value)

# Singleton default clock instance
clock = Clock()

