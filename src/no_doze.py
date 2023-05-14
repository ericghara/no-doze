import datetime
import logging
import os
import time
from datetime import datetime, timedelta
from typing import *

from src.config_provider import _config_yml
from src.sleep_inhibitor import SleepInhibitor
from src.trigger.implementations.plex import PlexInhibitor
from src.trigger.implementations.qbittorrent import QbittorrentInhibitor
from src.trigger.inhibiting_process import InhibitingProcess


class NoDoze:
    WHO = "No-Doze Service"
    WHY = "A monitored process/event is in progress."
    WHAT = "sleep"
    MODE = "block"  # "delay" | "block"
    SYS_INHIBIT_PROG = "systemd-inhibit"
    SYS_SLEEP_PROG = "sleep"

    def __init__(self, check_period_sec: float | int = None):
        self.log = logging.getLogger(type(self).__name__)
        if check_period_sec is None:
            check_period_sec = _config_yml.get("check_period_sec", 0)
        self.check_period: timedelta = timedelta(seconds=check_period_sec)
        self.inhibiting_processes = list()
        self._sleep_inhibitor: Optional[SleepInhibitor] = None

    def run(self) -> None:
        if not self._sleep_inhibitor:
            raise ValueError("This was not properly opened.  Use in a with block.")
        next_start: datetime = datetime.now()
        while True:
            inhibiting_processes = self._find_inhibitors()
            next_start = next_start + self.check_period
            if (inhibiting_processes):
                self._inhibit(inhibiting_processes=inhibiting_processes)
            else:
                self._no_inhibit()
            sleep_duration_sec = self._calc_sec_until(next_start)
            if sleep_duration_sec < 0:
                # probably system went to sleep and woke up
                self.log.debug(f"Caught a negative sleep duration: {sleep_duration_sec}")
                next_start = datetime.now()
                continue
            time.sleep(sleep_duration_sec)

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

    def _find_inhibitors(self) -> List[InhibitingProcess]:
        inhibited = list()
        for process in self.inhibiting_processes:
            if process.does_inhibit():
                inhibited.append(process)
        return inhibited

    def add_inhibitor(self, inhibitor: InhibitingProcess) -> None:
        """
        :param inhibitor:
        :return:
        :raise: ValueError if the provided trigger was already registered
        """
        if inhibitor in self.inhibiting_processes:
            raise ValueError(f"The trigger: {inhibitor.name} is already registered.")
        self.inhibiting_processes.append(inhibitor)

    def _inhibit(self, inhibiting_processes: List[InhibitingProcess]) -> bool:
        self.log.debug(f"Inhibition required for the next period, due to Inhibiting Processes: {inhibiting_processes}.")
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

    def _generate_why(self, inhibiting_processes: List[InhibitingProcess], until: datetime) -> str:
        process_names = list()
        for process in inhibiting_processes:
            process_names.append(process.name)
        return f"Monitored processes: {', '.join(process_names)} are preventing sleep until: {until.time()}"

    def _generate_inhibit_command(self, why: str, until: datetime) -> str:
        sleep_duration_sec = self._calc_sec_until(until)
        return f'{self.SYS_INHIBIT_PROG} --who="{self.WHO}" --what="{self.WHAT}" --why="{why}" --mode="{self.MODE}" ' \
               f'{self.SYS_SLEEP_PROG} {sleep_duration_sec}'


def main() -> None:
    logging.basicConfig(level=logging.DEBUG)
    with NoDoze() as no_doze:
        no_doze.add_inhibitor(PlexInhibitor())
        no_doze.add_inhibitor(QbittorrentInhibitor())
        no_doze.run()


if __name__ == "__main__":
    print(os.path.abspath(__file__))
    main()
