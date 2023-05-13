import logging
import traceback
from collections import namedtuple, deque
from math import inf
from typing import NamedTuple, Deque
from datetime import datetime, timedelta

from qbittorrentapi import Client

from src.config_provider import get_value
from src.sleep_inhibitor.inhibiting_process import InhibitingProcess

config_root_key = "qbittorrent"
username_key = "username"
password_key = "password"
host_key = "host_url"
download_key = "downloading"
seed_key = "seeding"
stalled_key = "period_min"
speed_key = "min_speed_kbps"


class TimeBytes(NamedTuple):
    time: datetime
    bytes: int


BYTES_PER_KB = 1024


class QbittorrentInhibitor(InhibitingProcess):
    """
    Allows inhibition based on average transfer rate over a period.  Uses a sliding window and session transfer statistics
    from the qBittorrent API to calculate the average rate.
    """

    def __init__(self):
        super().__init__("QBittorrent Transfer(s)")
        self._log = logging.getLogger(type(self).__name__)
        self._template = self._create_client_template()
        # download
        download_timeout = float(get_value([config_root_key, download_key, stalled_key], "0")) # 0 disables
        self._min_download_speed = float(get_value([config_root_key, download_key, speed_key], "inf"))
        self._validate_period_speed(period=download_timeout, min_speed=self._min_download_speed)
        self._download_period = timedelta(minutes=download_timeout)
        # seed
        seed_timeout = float(get_value([config_root_key, seed_key, stalled_key], "0")) # 0 disables
        self._min_seed_speed = float(get_value([config_root_key, seed_key, speed_key], "inf"))
        self._validate_period_speed(period=seed_timeout, min_speed=self._min_seed_speed)
        self._seed_period = timedelta(minutes=seed_timeout)

        self._download_history = deque()
        self._seed_history = deque()

    def does_inhibit(self) -> bool:
        if not self._min_download_speed or not self._min_seed_speed:
            # A disabled state, no network call is made, never inhibit
            return False
        self._update_history()
        if self._calc_mean_kbps_in_window(self._download_history, self._download_period) >= self._min_download_speed:
            return True
        return self._calc_mean_kbps_in_window(self._seed_history, self._seed_period) >= self._min_seed_speed

    def _calc_mean_kbps_in_window(self, history: Deque[TimeBytes], period: timedelta) -> float:
        if len(history) < 2:
            # first run, insufficient history
            return inf

        recent, old = history[0], history[-1]

        if recent.bytes < old.bytes or recent.time - old.time < period:
            # (qbittorrent was restarted) or (insufficient history)
            # qbittorrent was restarted: eventually old history will be cleaned, inhibit sleep until then
            # insufficient history: inhibit sleep until we have more data
            return inf

        delta_kb = (recent.bytes - old.bytes) / BYTES_PER_KB
        delta_sec = (recent.time - old.time).total_seconds()
        return delta_kb / delta_sec

    def _update_history(self) -> None:
        try:
            response = self._template.transfer_info()
        except Exception as e:
            self._log.info("Suppressed an error from template, run with debug to get full stacktrace.")
            self._log.debug(e)
            response = {}
        now = datetime.now()
        download_bytes = response.get("dl_info_data", 0)  # total bytes downloaded during session
        seed_bytes = response.get("up_info_data", 0)

        def clean_history(history: Deque[TimeBytes], period: timedelta):
            # removes expired history
            while len(history) > 2 and history[-1].time < (now - period) and history[-2].time <= (now - period):
                history.pop()
            # removes prior history when it appears qbittorrent has been restarted
            # while len(history) > 1 and history[-1].bytes > history[0].bytes:
            #     history.pop()

        def add_new(history: Deque[TimeBytes], num_bytes) -> None:
            history.appendleft(TimeBytes(time=now, bytes=num_bytes))

        add_new(self._download_history, download_bytes)
        clean_history(self._download_history, self._download_period)

        add_new(self._seed_history, seed_bytes)
        clean_history(self._seed_history, self._seed_period)


    def _validate_period_speed(self, period, min_speed) -> None:
        if min_speed != inf and period == 0 or period != 0 and min_speed == inf:
            raise ValueError(f"Improper configuration, {speed_key} and {stalled_key} contradict.  "
                             f"If a speed floor is set a period is required.")
        if period < 0 or min_speed < 0:
            raise ValueError("Durations and speeds must be >= 0.")

    def _create_client_template(self) -> Client:
        host_url = get_value([config_root_key, host_key])
        username = get_value([config_root_key, username_key], "")
        password = get_value([config_root_key, username_key], "")
        return Client(host=host_url, username=username, password=password)
