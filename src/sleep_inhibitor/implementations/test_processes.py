from sleep_inhibitor.inhibiting_process import InhibitingProcess


class AlwaysInhibits(InhibitingProcess):

    def __init__(self):
        super().__init__(type(self).__name__)

    def does_inhibit(self) -> bool:
        return True


class NeverInhibits(InhibitingProcess):

    def __init(self):
        super().__init__(type(self).__name__)

    def does_inhibit(self) -> bool:
        return False


