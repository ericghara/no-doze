import datetime
import logging
import time
from datetime import datetime, timedelta
from typing import *

from common import config_provider
from client.inhibiting_condition import InhibitingCondition
from client.inhibiting_condition_registrar import registrar
from common.priority_queue import PriorityQueue
from server.sleep_inhibitor import SleepInhibitor
import json
from common.message.transform import MessageEncoder
from common.message.messages import BindMessage, InhibitMessage
import glob
import signal
import os.path as path
import os
import re

class ScheduledCheck(NamedTuple):
    time: datetime
    inhibiting_process: InhibitingCondition

    def __lt__(self, other: 'ScheduledCheck'):
        return self.time < other.time


class NoDozeClient:

    DEFAULT_BASE_DIR = path.relpath("../")
    DEFAULT_CONNECTION_ATTEMPTS = 0
    FIFO_PREFIX = "FIFO_"
    FIFO_REATTEMPT_DELAY = timedelta(seconds=1)
    UNBIND_SIGNAL = signal.SIGUSR1

    def __init__(self, base_dir: path=DEFAULT_BASE_DIR, startup_delay: timedelta=timedelta(),
                 max_reconnections: int = DEFAULT_CONNECTION_ATTEMPTS,
                 reattempt_delay: timedelta=FIFO_REATTEMPT_DELAY):
        self._log = logging.getLogger(type(self).__name__)
        self._inhibiting_processes = list()
        self._schedule: Optional[PriorityQueue[ScheduledCheck]] = PriorityQueue()
        self._base_dir = base_dir
        self._startup_delay = startup_delay
        self._fifo_path: Optional[str] = None
        self._fifo: Optional[IO] = None
        self._connection_attempt = 0
        self._inhibit_until = datetime.now()
        self._max_reconnections = max_reconnections
        self._reattempt_delay = reattempt_delay
        self._run = True

    def send_message(self, obj: Any) -> int:
        """
        Sends message using FIFO.  Adds a newline delimiter to every message.
        Messages containing newlines are not supported.
        :param obj:
        :return: num bytes sent
        """
        if self._fifo is None:
            raise RuntimeError("FIFO not yet opened.")
        msg_str = json.dumps(obj, cls=MessageEncoder)+'\n'
        msg_b = msg_str.encode()
        self._fifo.write(msg_b)
        return len(msg_b)

    def _identify_fifo(self) -> path:
        matcher = re.compile(self.FIFO_PREFIX + r"(\d+)")
        found_fifo = None
        # add some max attempts? here too?
        while not found_fifo:
            num_fifo = 0
            for maybe_fifo in glob.glob(root_dir=self._base_dir, pathname=f"{self.FIFO_PREFIX}*"):
                if not matcher.match(maybe_fifo):
                    self._log.debug(f"Skipping: {maybe_fifo}.  Doesn't match expected FIFO naming.")
                else:
                    num_fifo += 1
                    found_fifo = maybe_fifo
                    self._log.debug(f"Discovered FIFO {found_fifo}")
            if num_fifo != 1:
                found_fifo = None
                self._log.info(f"Detected {num_fifo} connection candidates.  Waiting for: 1.")
                self._log.info(f"Reattempting in {self._reattempt_delay}")
                time.sleep(self._reattempt_delay.total_seconds())

        self._log.debug(f"Candidate for FIFO connection identified: {found_fifo}")
        return path.join(self._base_dir, found_fifo)

    def open_fifo(self):
        self._fifo = None
        while self._fifo is None:
            self._connection_attempt += 1
            if self._connection_attempt > self._max_reconnections:
                self._log.warning("Max connection attempts exceeded.")
                self.stop()
                return

            if self._connection_attempt != 1:
                self._log.info(f"Waiting {self._reattempt_delay} before reconnecting.")
                time.sleep(self._reattempt_delay.total_seconds())

            fifo_path = self._identify_fifo()
            try:
                self._fifo = open(fifo_path, mode="w+b", buffering=0)
                self._fifo_path = fifo_path
            except Exception as e:
                self._log.warning(f"Unable to open fifo: {fifo_path}", exc_info=e)
                self._fifo = None

        self.send_message(BindMessage(pid=os.getpid(), gid=os.getgid(), attempt=self._connection_attempt))

    def close_fifo(self) -> None:
        if self._fifo is None:
            return
        self._log.info(f"Closing FIFO: {self._fifo_path}")
        try:
            self._fifo.close()
        except Exception as e:
            self._log.warning("Encountered an error while closing the FIFO.", exc_info=e)

        self._fifo_path = None
        self._fifo = None


    def add_inhibitor(self, inhibitor: InhibitingCondition) -> None:
        """
        :param inhibitor:
        :return:
        :raise: ValueError if the provided plugin was already registered
        """
        if inhibitor in self._inhibiting_processes:
            raise ValueError(f"The plugin: {inhibitor.name} is already registered.")
        self._inhibiting_processes.append(inhibitor)
        self._schedule.offer(
            ScheduledCheck(time=datetime.now() + self._startup_delay, inhibiting_process=inhibitor))

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
                self._log.debug(
                    "Unable to keep up with schedule.  If system did not recently return from sleep there is a problem.")
                scheduled_time = datetime.now() + inhibiting_process.period()
            if inhibiting_process.does_inhibit():
                if scheduled_time > self._inhibit_until:
                    self._inhibit_until = scheduled_time
                    self._log.debug(
                        f"Process: {inhibiting_process} requires a new inhibition or extension of the current inhibition until: {scheduled_time}.")
                else:
                    self._log.debug(
                        f"Inhibition already satisfied: Process: {inhibiting_process} requires inhibition until {scheduled_time}.")
            self._schedule.offer(ScheduledCheck(time=scheduled_time, inhibiting_process=inhibiting_process))

    def _calc_sec_until(self, until: datetime) -> float:
        now = datetime.now()
        sec = (until - now).total_seconds()
        if (sec < 0):
            self._log.debug(f"Caught a negative sleep duration: {sec}")
            return 0
        return sec

    def _handle_period(self) -> None:
        """
        Updates state of `SleepInhibitor` if necessary

        *note* this was separated from `run` to facilitate testing.
        """
        next_check: datetime = self._schedule.peek().time
        sleep_duration_sec = self._calc_sec_until(next_check)
        time.sleep(sleep_duration_sec)
        self._handle_scheduled_checks()

    def run(self) -> None:
        if not self._inhibiting_processes:
            raise ValueError("Cannot start without any inhibiting conditions.  Check your configuration.")

        while self._run:
            if self._fifo is None:
                self.open_fifo()
                # give client a chance to reply to bind message (via a signal)
                time.sleep(self._reattempt_delay.total_seconds())
                continue
            self._handle_period()
            if self._inhibit_until > datetime.now():
                self.send_message(InhibitMessage(pid=os.getgid(), gid=os.getgid(),
                                                 expiry_timestamp=self._inhibit_until))


    def stop(self):
        """
        This wille eventually cause run to exit, the next time it wakes up from sleep.  Intended to be thread safe.
        :return:
        """
        self._run = False


    def __enter__(self) -> 'Server':
        # currently a no op
        return self

    def __exit__(self, exc_type: any, exc_val: any, exc_tb: any):
        self.close_fifo()


def main() -> None:
    registrar.scan()
    with NoDozeClient() as client:
        # todo setup config provider
        signal.signal(handler=lambda sig, frame: client.close_fifo(), signalnum=NoDozeClient.UNBIND_SIGNAL)
        for inhibiting_process in registrar:
            client.add_inhibitor(inhibiting_process)
        client.run()

if __name__ == "__main__":
    logging.basicConfig(level="INFO")
    main()

















