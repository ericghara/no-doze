from abc import ABC
from datetime import timedelta


class InhibitingProcess(ABC):

    def __init__(self, name: str, period: timedelta):
        super().__init__()
        self.name: str = name
        if period.total_seconds() <= 0:
            raise ValueError("Period must be positive.")
        self._period: timedelta = period

    def does_inhibit(self) -> bool:
        pass

    def period(self) -> timedelta:
        return self._period

    def __str__(self):
        return self.name

    def __repr__(self):
        return f"InhibitingProcess(name={self.name})"
