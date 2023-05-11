import datetime
import logging
import os
import signal
import subprocess
import time
from datetime import datetime, timedelta
from typing import *

from sleep_inhibitor.implementations.plex import PlexInhibitor
from inhibiting_process import InhibitingProcess

class NoDoze:
    WHO = "No-Doze Service"
    WHAT = "sleep"
    MODE = "block"  # "delay" | "block"
    SYS_INHIBIT_PROG = "systemd-inhibit"
    SYS_SLEEP_PROG = "sleep"
    PERIOD_OVERLAP = 1

    def __init__(self, check_period_sec: float | int):
        self.log = logging.getLogger(type(self).__name__)
        self.check_period: timedelta = timedelta(seconds=check_period_sec)
        self.check_period_with_overlap = self.check_period + timedelta(seconds=self.PERIOD_OVERLAP)
        self.inhibiting_processes = list()
        # clean shutdown
        for _signal in signal.SIGINT, signal.SIGTERM:
            signal.signal(_signal, self.close)

    def run(self) -> None:
        next_start: datetime = datetime.now()
        while True:
            inhibiting_processes = self._find_inhibitors()
            next_start = next_start + self.check_period
            if (inhibiting_processes):
                logging.debug(f"Inhibiting Processes: {inhibiting_processes}")

                self._inhibit(inhibiting_processes=inhibiting_processes,
                              until=next_start)
            sleep_duration_sec = self._calc_sec_until(next_start)
            if sleep_duration_sec < 0:
                # probably system went to sleep and woke up
                logging.debug(f"Caught a negative sleep duration: {sleep_duration_sec }")
                next_start = datetime.now()
                continue
            time.sleep(sleep_duration_sec)

    def close(self) -> None:
        pass

    def _calc_sec_until(self, until: datetime) -> float:
        now = datetime.now()
        sec = (until-now).total_seconds()
        if (sec < 0):
            logging.debug(f"Caught a negative sleep duration: {sec}")
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
        :raise: ValueError if the provided sleep_inhibitor was already registered
        """
        if inhibitor in self.inhibiting_processes:
            raise ValueError(f"The sleep_inhibitor: {inhibitor.name} is already registered.")
        self.inhibiting_processes.append(inhibitor)

    def _inhibit(self, inhibiting_processes: List[InhibitingProcess], until: datetime) -> subprocess.Popen:
        why = self._generate_why(inhibiting_processes=inhibiting_processes, until=until)
        inhibit_command = self._generate_inhibit_command(why=why, until=until)
        self.log.debug(f"Runnning: {inhibit_command}")
        return subprocess.Popen(inhibit_command, shell=True)

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
    no_doze = NoDoze(10)
    no_doze.add_inhibitor(PlexInhibitor())
    no_doze.run()


if __name__ == "__main__":
    print(os.path.abspath(__file__))
    main()
