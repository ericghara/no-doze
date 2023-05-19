from abc import ABC
from datetime import timedelta

from core import config_provider


class InhibitingCondition(ABC):
    """
    Defines the interface of classes that can request sleep to be inhibited.  An `InhibitingCondition` is checked at defined
    `periods` by NoDoze.  The `period` is queried during start-up and remains fixed (aside from during system sleep
    or hibernation).

    Each period, `does_inhibit` will be called once.  A response of `True` guarantees that the NoDoze will inhibit
    sleep.  A response of `False` indicates that *this* process does not require sleep inhibition, but other processes
    may.

    The duration of sleep is the `period`.  An `ImplementingProcess` that returns `True` on every `does_inhibit` call
    will inhabit sleep forever.

    Implementors should ensure that calls to `does_inhibit` complete on the order of milliseconds.  InhibitingConditions
    are checked sequentially and long-running calls to `does_inhibit` will prevent NoDoze from calling inhibitors during
    their scheduled periods.

    Configurations for InhibitingConditions should be included in the `resources.config.yml` file.  the `config_provider`
    module includes useful functions to parse fields from the `config.yml`.  For consistency across implementations,
    durations in the configuration should be specified in minutes wherever possible.

    In order to use an implementation, NoDoze is able to auto-discover `InhibitingConditions` in the `plugin`
    package.  All implementations should be a module (i.e. `my_implementation.py`) and placed into `plugin` folder.
    Each implementation should also include a `register` function that is called with the module is discovered.  Details
    of the register function implementation are provided below.
    """

    def __init__(self, name: str, period: timedelta):
        """
        :param name: name, used for logging
        :param period: duration of sleep inhibition and period between `does_inhibit` checks.  set to `datetime.max` to disable,
        never set to less than ~5 seconds.
        """
        super().__init__()
        self.name: str = name
        if period.total_seconds() <= 0:
            raise ValueError("Period must be positive.")
        self._period: timedelta = period

    def does_inhibit(self) -> bool:
        """
        Reports to NoDoze that sleep should be inhibited.  Called once per period.  If `True` is returned it is guaranteed
        that NoDoze will inhibit sleep for the period.
        :return:
        """
        pass

    def period(self) -> timedelta:
        """
        Duration of time between calls to `does_inhibit`. Also is the duration that sleep will be inhibited for when
        `does_inhibit` returns `True`
        :return:
        """
        return self._period

    def __str__(self):
        return self.name

    def __repr__(self):
        return f"InhibitingCondition(name={self.name})"


def register(registrar: 'InhibitingConditionRegistrar') -> None:
    """
    Include this to make an implementation of InhibitingCondition auto-discoverable by NoDoze. `register` should construct
    an InhibitingCondition and then pass it to the registrar with `registrar.accept`.

    It is possible to register multiple InhibitingConditions in a call to register.

    :param registrar: an InhibitingConditionRegistrar singleton
    """
    if config_provider.key_exists(["demo_inhibiting_condition"]):  # check if user has configured this plugin
        registrar.accept(InhibitingCondition(name="Example", period=timedelta.max))  # add plugin to registrar
