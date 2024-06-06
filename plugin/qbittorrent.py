import logging
import sys
from datetime import datetime, timedelta
from enum import Enum
from typing import NamedTuple, Optional

from qbittorrentapi import Client

from common import config_provider
from client.inhibiting_condition import InhibitingCondition

logging_level_key = "logging_level"
config_root_path = ("plugins", "qbittorrent")
username_key = "username"
password_key = "password"
host_key = "host_url"
download_key = "downloading"
seed_key = "seeding"
period_min_key = "period_min"
speed_key = "min_speed_kbps"


class TimeBytes(NamedTuple):
    time: datetime
    bytes: int


BYTES_PER_KB = 1024


class QbittorrentInhibitor(InhibitingCondition):

    """
    An inhibitor that uses Web UI API's to inhibit sleep based on seeding or download rates. The Web UI *must* be
    enabled in the qBittorrent configuration in order for this to work.

    Rates are used instead of a simple check of active downloads/uploads because often torrents can be *essentially*
    stuck making almost no progress in these cases some users may want sleep to occur.  Users who don't care about this
    should set the transfer threshold to a very low number such as 0 or 1 kbps.

    Keep in mind torrent transfer rates can fluctuate significantly, so it's not a good idea to pick very short periods,
    i.e. 1 minute.  The transfer rate used to determine if sleep should be inhibited is the simple average transfer rate
    over the period.
    """
    class Channel(Enum):
        SEEDING = "seeding"
        DOWNLOADING = "downloading"

    def __init__(self, channel: Channel):
        """
        Can be configured to monitor download or seeding rates.  To monitor both, two separate QbittorrentInhibitors
        should be constructed.
        :param channel: a `Channel` enum
        """
        self._channel: QbittorrentInhibitor.Channel = channel
        name = f"{type(self).__name__} - {channel.value}"
        super().__init__(name=name, period=self._get_period())
        self._log = logging.getLogger(name)
        self._template = self._create_client_template()
        ## Initialize channel specific variables
        self._min_speed_kbps: Optional[float] = self._get_min_speed_kbps()
        self._data_transferred_key: Optional[str] = self._get_data_transferred_key()

        self._last_reading: TimeBytes = TimeBytes(time=datetime.now(),
                                                  bytes=sys.maxsize)  # sentinel, forces inhibition for first period

        if config_provider.get_value([logging_level_key], "INFO") == "INFO":
            logging.getLogger('urllib3').setLevel(logging.CRITICAL) # very chatty when unable to connect

    def _get_channel_key(self) -> str:
        if self._channel is self.Channel.SEEDING:
            return seed_key
        elif self._channel is self.Channel.DOWNLOADING:
            return download_key
        else:
            raise ValueError("Unrecognized enum. Something is very wrong.")

    def _get_period(self) -> timedelta:
        """
        If no key found effectively disables by setting period to 'sys.maxvalue'
        :return:
        """
        return config_provider.get_period_min(key_path=[*config_root_path, self._get_channel_key(), period_min_key], default=timedelta.max)

    def _get_min_speed_kbps(self) -> float:
        """
        If no key found effectively disables by setting max speed to `inf`
        :return:
        """
        raw_val = config_provider.get_value([*config_root_path, self._get_channel_key(), speed_key], 'inf')
        return float(raw_val)

    def _get_data_transferred_key(self) -> str:
        return 'dl_info_data' if self._channel is QbittorrentInhibitor.Channel.DOWNLOADING else "up_info_data"

    def _create_client_template(self) -> Client:
        host_url = config_provider.get_value([*config_root_path, host_key])
        username = config_provider.get_value([*config_root_path, username_key], "")
        password = config_provider.get_value([*config_root_path, username_key], "")
        return Client(host=host_url, username=username, password=password)

    def _fetch_reading(self) -> TimeBytes:
        try:
            response = self._template.transfer_info()
        except Exception as e:
            self._log.debug("Suppressed an error while fetching transfer info", e)
            response = {}
        transferred = response.get(self._data_transferred_key, 0)
        return TimeBytes(time=datetime.now(), bytes=transferred)

    def does_inhibit(self) -> bool:
        cur_reading: TimeBytes = self._fetch_reading()
        seconds_elapsed = (cur_reading.time - self._last_reading.time).total_seconds()
        byte_delta = cur_reading.bytes - self._last_reading.bytes
        self._last_reading = cur_reading
        if seconds_elapsed > (1.5 * self.period().total_seconds()):
            self._log.debug(
                "Excessive time passed between periods.  If system did not just wake up from sleep this indicates a problem.")
            # we need more data, inhibit sleep.
            return True
        if byte_delta < 0:
            self._log.debug(
                "Encountered a negative byte delta.  This could indicate a problem if qbittorrent was not recently restarted.")
            # we need more data, inhibit sleep.
            return True
        if seconds_elapsed <= 0:
            raise ValueError("Time between readings was <= 0")
        return byte_delta / (seconds_elapsed * BYTES_PER_KB) >= self._min_speed_kbps

def register(registrar: 'InhibtingConditionRegistrar'):
    """
    Registers properly configured `QbittorrentInhibitors`.  May register multiple `QbittorrentInhibitors`.
    :param registrar:
    :return:
    """
    if config_provider.key_exists([*config_root_path, "downloading"]):
        registrar.accept(QbittorrentInhibitor(channel=QbittorrentInhibitor.Channel.DOWNLOADING))
    else:
        logging.debug("Skipping registration of 'qBittorrent - Downloading'. Configuration is absent from the config.yml.")
    if config_provider.key_exists(["qbittorrent", "seeding"]):
        registrar.accept(QbittorrentInhibitor(channel=QbittorrentInhibitor.Channel.SEEDING))
    else:
        logging.debug("Skipping registration of 'qBittorrent - Seeding'. Configuration is absent from the config.yml.")