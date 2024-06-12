import logging
from typing import *
from datetime import datetime
from threading import Timer, Lock
from server.sleep_inhibitor import SleepInhibitor

class ScheduledInhibition:

    """
    Needs to be opened/closed with `__enter__` and `__exit__`
    """
    def __init__(self, who: str, why: str):
        self._log = logging.getLogger(type(self).__name__)
        self._who = who
        self._why = why
        self._schedule_lock = Lock()
        # optionals only None when closed
        self._inhibit_until: Optional[datetime] = None
        self._sleep_inhibitor: Optional[SleepInhibitor] = None
        self._timer: Optional[Timer] = None

    def set_inhibitor(self, until: datetime) -> bool:
        """
        Acquire a lock and set the inhibitor until the given time.  If inhibitor is not already set or
        is already set to a later time, does nothing; otherwise, begins an inhibition and spawns child thread
        (timer) which releases the inhibition lock.
        :param until: time to sleep until
        :return: True if a new inhibition started or an existing period was extended else False
        """

        # avoid taking the lock if we can (logic repeated in critical section as well)
        if max(datetime.now(), self._inhibit_until) >= until:
            self._log.debug(f"Ignoring an inhibition.  Already scheduled to inhibit to a >= time.")
            return False

        with self._schedule_lock:
            if not all([self._inhibit_until, self._sleep_inhibitor, self._timer]):
                # At shutdown these could be None due to race between timer thread and main thread.
                # also protects against misuse
                self._log.warning("Refusing to set inhibitor.  Instance not opened/entered.  Shutting down?")
                return False
            if max(datetime.now(), self._inhibit_until) >= until:
                self._log.debug(f"Ignoring an inhibition.  Already scheduled to inhibit to a >= time.")
                return False

            self._log.debug("Entering a new/extending an existing inhibition.")
            self._timer.cancel()
            self._inhibit_until = until
            self._sleep_inhibitor.inhibit_sleep()
            self._timer = Timer(interval=(self._inhibit_until-datetime.now()).total_seconds(),
                                function=self._create_unlock_callback())
            self._timer.start()
            return True

    def _create_unlock_callback(self) -> Callable:
        expected_until = self._inhibit_until  # capture
        return lambda: self.unset_inhibitor(expected_until)

    def unset_inhibitor(self, set_at: datetime, force: bool=False) -> bool:
        """
        Acquires lock and ends sleep inhibition if it is ongoing.
        :param set_at: inhibition time set was called with
        :param force: ignores set_at time.  Inhibitor will be unset no matter what
        :return: if a state transition actually occurred (set -> unset)
        """
        #need to check if anything is None b/c of shutdown
        with self._schedule_lock:
            if not all([self._inhibit_until, self._sleep_inhibitor, self._timer]):
                self._log.warning("Refusing to unset inhibitor. Instance not opened/entered. Shutting down?")
                return False
            if set_at != self._inhibit_until and not force:
                # there was a race, another thread got lock first and started a new inhibition
                self._log.debug("Not stopping inhibition.  Another has been scheduled.")
                return False
            self._sleep_inhibitor.allow_sleep()
            return True

    def inhibit_until(self) -> datetime:
        return self._inhibit_until

    def __enter__(self) -> 'ScheduledInhibition':
        self._inhibit_until = datetime.now()
        self._sleep_inhibitor = SleepInhibitor(who=self._who, why=self._why)
        self._timer = Timer(0, lambda: None) # dummy
        self._timer.start()
        self._sleep_inhibitor.__enter__() # connect to dbus...
        return self


    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._timer is not None:
            self._timer.cancel()
        if self._sleep_inhibitor is not None:
            self._sleep_inhibitor.__exit__(None, None, None)
        with self._schedule_lock:
            self._inhibit_until = None
            self._timer = None
            self._sleep_inhibitor = None


