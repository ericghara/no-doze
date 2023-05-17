import datetime
import logging
import os
import time
from datetime import datetime, timedelta
from typing import *

from src import config_provider
from src.inhibiting_process_registrar import registrar
from src.priority_queue import PriorityQueue
from src.sleep_inhibitor import SleepInhibitor
from src.trigger.inhibiting_condition import InhibitingCondition


class ScheduledCheck(NamedTuple):
    time: datetime
    inhibiting_process: InhibitingCondition

    def __lt__(self, other: 'ScheduledCheck'):
        return self.time < other.time


class NoDoze:
    WHO = "No-Doze Service"
    WHY = "A monitored process/event is in progress."
    WHAT = "sleep"
    MODE = "block"  # "delay" | "block"
    _STARTUP_DELAY_KEY = "startup_delay_min"

    def __init__(self):
        self.log = logging.getLogger(type(self).__name__)
        self.inhibiting_processes = list()
        self._startup_delay_min = config_provider.get_period_min(key_path=[self._STARTUP_DELAY_KEY],
                                                                 default=timedelta(minutes=0))
        self._schedule: Optional[PriorityQueue[ScheduledCheck]] = PriorityQueue()
        self._sleep_inhibitor: Optional[SleepInhibitor] = None
        self._inhibit_until = datetime.now()

    def run(self) -> None:
        if not self._sleep_inhibitor:
            raise ValueError("This was not properly opened.  Use in a with block.")
        if not self.inhibiting_processes:
            raise ValueError("Cannot start without any inhibiting processes.  Check your configuration.")

        while True:
            self._handle_period()

    def _handle_period(self) -> None:
        """
        Updates state of `SleepInhibitor` if necessary

        *note* this was separated from `run` to facilitate testing.
        """

        next_check: datetime = self._schedule.peek().time
        sleep_duration_sec = self._calc_sec_until(next_check)
        time.sleep(sleep_duration_sec)
        self._handle_scheduled_checks()

        if self._inhibit_until > datetime.now():
            self._inhibit()
        else:
            self._no_inhibit()

    def _handle_scheduled_checks(self) -> None:
        """
        Runs scheduled checks and updates the schedule with checks to be run in the future.
        *Note:* length of the schedule changes consistent between periods.  Every scheduled check that is
        removed is updated and reinserted at a future time in the schedule.
        """
        while datetime.now() >= self._schedule.peek().time:
            last_scheduled_time, inhibiting_process = self._schedule.poll()
            scheduled_time = last_scheduled_time + inhibiting_process.period()
            # We woke up from sleep or something delayed checking
            if scheduled_time < datetime.now():
                self.log.debug(
                    "Unable to keep up with schedule.  If system did not recently return from sleep there is a problem.")
                scheduled_time = datetime.now() + inhibiting_process.period()
            if inhibiting_process.does_inhibit():
                if scheduled_time > self._inhibit_until:
                    self._inhibit_until = scheduled_time
                    self.log.debug(
                        f"Process: {inhibiting_process} requires a new inhibition or extension of the current inhibition until: {scheduled_time}.")
                else:
                    self.log.debug(
                        f"Inhibition already satisfied: Process: {inhibiting_process} requires inhibition until {scheduled_time}.")
            self._schedule.offer(ScheduledCheck(time=scheduled_time, inhibiting_process=inhibiting_process))

    def __enter__(self) -> 'NoDoze':
        if self._sleep_inhibitor:
            raise ValueError("Cannot re-open this resource, it is already open.")
        self._sleep_inhibitor = SleepInhibitor(who=self.WHO, why=self.WHY)
        self._sleep_inhibitor.__enter__()
        return self

    def __exit__(self, exc_type: any, exc_val: any, exc_tb: any):
        if self._sleep_inhibitor:
            self._sleep_inhibitor.__exit__(exc_type=exc_type, exc_val=exc_val, exc_tb=exc_tb)
        self._sleep_inhibitor = None

    def _calc_sec_until(self, until: datetime) -> float:
        now = datetime.now()
        sec = (until - now).total_seconds()
        if (sec < 0):
            self.log.debug(f"Caught a negative sleep duration: {sec}")
            return 0
        return sec

    def add_inhibitor(self, inhibitor: InhibitingCondition) -> None:
        """
        :param inhibitor:
        :return:
        :raise: ValueError if the provided trigger was already registered
        """
        if inhibitor in self.inhibiting_processes:
            raise ValueError(f"The trigger: {inhibitor.name} is already registered.")
        self.inhibiting_processes.append(inhibitor)
        self._schedule.offer(ScheduledCheck(time=datetime.now()+self._startup_delay_min, inhibiting_process=inhibitor))

    def _inhibit(self) -> bool:
        self.log.debug(f"Inhibition required for the next period.")
        if (self._sleep_inhibitor.is_inhibiting()):
            self.log.debug("Continuing an ongoing sleep inhibition, no new lock taken.")
            return False
        else:
            self.log.debug("Beginning a new sleep inhibition, lock will be taken.")
            self._sleep_inhibitor.inhibit_sleep()
            return True

    def _no_inhibit(self) -> bool:
        self.log.debug(f"No Inhibiting processes.  Sleep allowed for next period.")
        if self._sleep_inhibitor.is_inhibiting():
            self.log.debug("Ending the inhibition currently in place. Returning a sleep inhibition lock.")
            self._sleep_inhibitor.allow_sleep()
            return True
        else:
            self.log.debug("No sleep inhibition is currently in place.  Doing nothing.")
            return False


def main() -> None:
    registrar.scan()
    with NoDoze() as no_doze:
        for inhibiting_process in registrar:
            no_doze.add_inhibitor(inhibiting_process)
        no_doze.run()


if __name__ == "__main__":
    print(os.path.abspath(__file__))
    main()
