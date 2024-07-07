from datetime import timedelta
from typing import Optional

from client.inhibiting_condition import InhibitingCondition

"""
These implementations are for testing.  They **do not** AutoRegister or pull properties from the config.yml.  
While they could be useful as templates for custom implementations, it would be useful to refer to some other 
implementations as well.
"""

class AlwaysInhibits(InhibitingCondition):

    def __init__(self, period: timedelta):
        super().__init__(name=type(self).__name__, period=period)

    def does_inhibit(self) -> bool:
        return True


class NeverInhibits(InhibitingCondition):

    def __init__(self, period: timedelta):
        super().__init__(name=type(self).__name__, period=period)

    def does_inhibit(self) -> bool:
        return False


class ProgrammableInhibitor(InhibitingCondition):
    """
    An inhibitor where the return value of `does_inhibit` should be set before each call.  Calling `does_inhibit` pops
    the previously set value.  A subsequent call to `set_next` must be made before calling `does_inhibit` again.  Return
    values *cannot* be stacked.  They should be sequentially, set then polled.
    """

    def __init__(self, period: timedelta):
        super().__init__(name=type(self).__name__, period=period)
        self._next: Optional[bool] = None
        self._was_called = False

    def does_inhibit(self) -> bool:
        if self._next is None:
            raise ValueError("Must set next value each time before calling.")
        next_val = self._next
        self._next = None
        self._was_called = True
        return next_val

    def set_next(self, next_val: bool) -> None:
        if self._next is not None:
            raise ValueError("Previously set value was never polled.")
        self._was_called = False
        self._next = next_val

    def was_called(self) -> bool:
        """
        :return: that does_inhibit was called since last call to set_next
        """
        return self._was_called
