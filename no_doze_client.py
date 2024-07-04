#!/usr/bin/env python

import argparse
import datetime
import glob
import json
import logging
import os
import os.path as path
import re
import select
import signal
from datetime import datetime, timedelta
from select import poll
from typing import *

from client.inhibiting_condition import InhibitingCondition
from client.inhibiting_condition_registrar import registrar
from common import config_provider
from common.config_provider import CastFn
from common.message.messages import BindMessage, InhibitMessage
from common.message.transform import MessageEncoder
from common.priority_queue import PriorityQueue

# YAML config keys
CLIENT_ROOT_KEY = "general"
LOGGING_LEVEL_KEY = "logging_level"
BASE_DIR_KEY = "base_dir"
RETRY_DELAY_KEY = "retry_delay_sec"
STARTUP_DELAY_KEY = "startup_delay_min"

# Global defaults
DEFAULT_CONFIG_PATH = "resources/no-doze-client.yml"


class ScheduledCheck(NamedTuple):
    time: datetime
    inhibiting_process: InhibitingCondition

    def __lt__(self, other: 'ScheduledCheck'):
        return self.time < other.time


class NoDozeClient:

    DEFAULT_BASE_DIR = path.relpath("./")
    DEFAULT_CONNECTION_ATTEMPTS = 3
    DEFAULT_STARTUP_DELAY = timedelta()
    FIFO_PREFIX = "FIFO_"
    RETRY_DELAY = timedelta(seconds=1)
    UNBIND_SIGNAL = signal.SIGUSR1
    ABOUT_TO_SLEEP_SIGNAL = signal.SIGRTMIN + 0

    def __init__(self, base_dir: path=DEFAULT_BASE_DIR, startup_delay: timedelta=timedelta(),
                 retry_delay: timedelta=RETRY_DELAY):
        self._log = logging.getLogger(type(self).__name__)
        self._inhibiting_processes = list()
        self._schedule: Optional[PriorityQueue[ScheduledCheck]] = PriorityQueue()
        self._base_dir = base_dir
        self._startup_delay = startup_delay
        self._fifo_path: Optional[str] = None
        self._fifo: Optional[IO] = None
        self._inhibit_until = datetime.now()
        self._retry_delay = retry_delay
        self._sig_w_fd: Optional[int] = None
        self._sig_r_fd: Optional[int] = None
        self._poll: Optional[poll] = None
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
        # The gist of the logic is to wait until there is only one fifo available
        # there *are* edge cases, but they should be quite rare as the daemon in all but extreme cases
        # clears deletes its fifo on shutdown and a new daemon clears stale fifos on startup
        matcher = re.compile(self.FIFO_PREFIX + r"(\d+)")
        num_fifo = 0
        found_fifo = None
        for maybe_fifo in glob.glob(root_dir=self._base_dir, pathname=f"{self.FIFO_PREFIX}*"):
            if not matcher.match(maybe_fifo):
                self._log.debug(f"Skipping: {maybe_fifo}.  Doesn't match expected FIFO naming.")
            else:
                num_fifo += 1
                found_fifo = maybe_fifo
                self._log.debug(f"Discovered FIFO {found_fifo}")

        if num_fifo != 1:
            self._log.info(f"Detected {num_fifo} connection candidates.  Waiting for one.")
            return None
        self._log.debug(f"Candidate for FIFO connection identified: {found_fifo}")
        return path.join(self._base_dir, found_fifo)

    def open_fifo(self) -> bool:
        fifo_path = self._identify_fifo()
        if fifo_path is None:
            return False
        try:
            self._fifo = open(fifo_path, mode="w+b", buffering=0)
            self._fifo_path = fifo_path
        except Exception as e:
            self._log.warning(f"Unable to open fifo: {fifo_path}", exc_info=e)
            self._fifo = None
        if self._fifo:
            self.send_message(BindMessage(pid=os.getpid(), uid=os.getuid()))
            self._log.info("Client connected to daemon.")
            return True
        return False

    def close_fifo(self) -> None:
        """
        Safe to call weather or not fifo is open
        :return:
        """
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

    def _handle_scheduled_checks(self) -> bool:
        """
        Runs scheduled checks and updates the schedule with checks to be run in the future.
        *Note:* length of the schedule changes consistent between periods.  Every scheduled check that is
        removed is updated and reinserted at a future time in the schedule.
        :return: if a new period of sleep should be started or an existing period should be extended
        """
        sleep_increased = False
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
                    sleep_increased = True
                    self._log.debug(
                        f"Process: {inhibiting_process} requires a new inhibition or extension of the current inhibition until: {scheduled_time}.")
                else:
                    self._log.debug(
                        f"Inhibition already satisfied: Process: {inhibiting_process} requires inhibition until {scheduled_time}.")
            self._schedule.offer(ScheduledCheck(time=scheduled_time, inhibiting_process=inhibiting_process))
        return sleep_increased

    def _handle_unscheduled_checks(self) -> bool:
        """
        For "last gasp" checks before sleep.  Does not touch the schedule at all.  Simply checks all
        inhibiting processes and updates _sleep_until respectively.
        :return: true if sleep inhibition required else false
        """
        sleep_increased = False
        for inhibiting_process in self._inhibiting_processes:
            if inhibiting_process.does_inhibit():
                scheduled_time = datetime.now() + inhibiting_process.period()
                if scheduled_time > self._inhibit_until:
                    self._inhibit_until = scheduled_time
                    sleep_increased = True
        return sleep_increased

    def _calc_sec_until(self, until: datetime) -> float:
        now = datetime.now()
        sec = (until - now).total_seconds()
        if (sec < 0):
            self._log.debug(f"Caught a negative sleep duration: {sec}. Startup?")
            return 0
        return sec

    def _read_signal(self, fd: int) -> int:
        """
        Get signal (single byte) or return -1 on error
        :param fd:
        :return:
        """
        sig = -1
        try:
            sig = os.read(fd, 1)[0]
        except Exception as e:
            self._log.warning(f"Error while reading signal.", exc_info=e)
        return sig

    def run(self) -> None:
        if not self._inhibiting_processes:
            raise ValueError("Cannot start without any inhibiting conditions.  Check your configuration.")
        while self._run:

            if self._fifo is None and not self.open_fifo():
                # no fifo don't poll at normal interval
                next_check_ms = round(self._calc_sec_until(datetime.now() + self.RETRY_DELAY) * 1000)
            else:
                next_check_ms = round(self._calc_sec_until(self._schedule.peek().time) * 1_000)

            events = self._poll.poll(next_check_ms)
            if events:
                # some interrupt
                for fd, _ in events:
                    if fd != self._sig_r_fd:
                        raise RuntimeError(f"Unknown file descriptor: {fd}")
                    sig = self._read_signal(fd)
                    if sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
                        self._log.info(f"Caught signal: {sig}. Starting Shutdown.")
                        self._run = False
                        break
                    elif self._fifo is None:
                        # without connection, we can't really do anything with other signals, so just drop
                        continue
                    elif sig == self.ABOUT_TO_SLEEP_SIGNAL:
                        if self._handle_unscheduled_checks():
                            self.send_message(InhibitMessage(pid=os.getpid(), uid=os.getuid(),
                                                             expiry_timestamp=self._inhibit_until))
                    elif sig == self.UNBIND_SIGNAL:
                        self.close_fifo(),
                    else:
                        self._log.info(f"Caught unrecognized signal: {sig}. Ignoring.")

            if self._run and self._fifo is not None and datetime.now() >= self._schedule.peek().time:
                if self._handle_scheduled_checks():
                    self.send_message(InhibitMessage(pid=os.getpid(), uid=os.getuid(),
                                                     expiry_timestamp=self._inhibit_until))



    def stop(self):
        """
        This will eventually cause run to exit, the next time it wakes up from sleep.  Intended to be thread safe.
        :return:
        """
        self._run = False


    def __enter__(self) -> 'NoDozeClient':
        if any((self._poll, self._fifo)):
            raise RuntimeError('Cannot reopen resource. Already Open.')
        self._sig_r_fd, self._sig_w_fd = os.pipe2(os.O_NONBLOCK)
        self._poll = poll()
        self._poll.register(self._sig_r_fd, select.POLLIN)
        signal.set_wakeup_fd(self._sig_w_fd)
        for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP, signal.SIGQUIT, signal.SIGALRM,
                    self.ABOUT_TO_SLEEP_SIGNAL, self.UNBIND_SIGNAL):
            # need to handle signals for wakeup_fd redirection to actually work
            signal.signal(signalnum=sig,
                          handler=lambda n, f: self._log.debug(f"Caught signal: {n}. Redirecting to pipe."))
        return self

    def __exit__(self, exc_type: any, exc_val: any, exc_tb: any):
        self.close_fifo()
        try:
            signal.set_wakeup_fd(-1)
            os.close(self._sig_w_fd)
            os.close(self._sig_r_fd)
        except Exception as e:
            self._log.warning("Unable to close read/write signal pipe(s)", exc_info=e)
        finally:
            self._sig_w_fd = None
            self._signal_r_fd = None
        self._poll = None


def main() -> None:
    base_dir = config_provider.get_value([CLIENT_ROOT_KEY, BASE_DIR_KEY], "./")
    retry_delay = config_provider.get_value([CLIENT_ROOT_KEY, RETRY_DELAY_KEY],
                                               cast_fn=CastFn.to_timedelta_sec,
                                               default=NoDozeClient.RETRY_DELAY)
    startup_delay = config_provider.get_value([CLIENT_ROOT_KEY, STARTUP_DELAY_KEY],
                                                 cast_fn=CastFn.to_timedelta_min,
                                                 default=NoDozeClient.DEFAULT_STARTUP_DELAY)
    registrar.scan()
    with NoDozeClient(base_dir=base_dir, retry_delay=retry_delay,
                      startup_delay=startup_delay) as client:
        for inhibiting_process in registrar:
            client.add_inhibitor(inhibiting_process)
        client.run()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="no_doze_client",
        description="Inhibit sleep based on plugins.  Communicates with no_doze_d.",
    )
    parser.add_argument('-c', '--config', type=str, help="path to config file",
                        default=DEFAULT_CONFIG_PATH)
    args = parser.parse_args()
    config_provider.load_file(path.expanduser(args.config))
    logging.basicConfig(level=config_provider.get_value([CLIENT_ROOT_KEY, LOGGING_LEVEL_KEY], "INFO"))
    if os.getuid() == 0:
        logging.info("no_doze_client does not need to be run as root. Consider reconfiguring.")
    main()

















