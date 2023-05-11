from abc import ABC


class InhibitingProcess(ABC):

    def __init__(self, name: str):
        super().__init__()
        self.name = name

    def does_inhibit(self) -> bool:
        pass

    def __str__(self):
        return self.name

    def __repr__(self):
        return f"InhibitingProcess(name={self.name})"


