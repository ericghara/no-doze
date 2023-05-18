import time
from time import sleep
from unittest import TestCase
from unittest.mock import Mock, patch

from core import config_provider
from plugin.qbittorrent import QbittorrentInhibitor


class TestQbittorrentInhibitorSingleChannel(TestCase):
    single_channel_yml = """
    qbittorrent:
        host_url: "http://test:1234"
        username: "test"
        password: "123456789"
        downloading:
            period_min: .0005 # 30 ms
            min_speed_kbps: 100 # or 3072 bytes / 30 ms
    """

    def setUp(self) -> None:
        config_provider._load_string(self.single_channel_yml)
        self.template_mock = Mock()
        self.qb_client_patch = patch("plugin.qbittorrent.Client",
                                     return_value=self.template_mock).start()
        self.inhibitor = QbittorrentInhibitor(channel=QbittorrentInhibitor.Channel.DOWNLOADING)

    def tearDown(self) -> None:
        for patch in self.qb_client_patch,:
            patch.stop()

    def _set_next_transfer_info_response(self, download_bytes: int) -> None:
        self.template_mock.transfer_info = lambda: {"dl_info_data": download_bytes}

    def test_does_inhibit_returns_true_on_first_call(self):
        self._set_next_transfer_info_response(download_bytes=100)
        self.assertTrue(self.inhibitor.does_inhibit())

    def test_does_inhibit_returns_true_when_insufficient_history(self):
        self._set_next_transfer_info_response(download_bytes=0)
        self.inhibitor.does_inhibit()
        sleep(0.015)
        self._set_next_transfer_info_response(download_bytes=4000)
        self.assertTrue(self.inhibitor.does_inhibit())

    def test_does_inhibit_returns_true_when_sufficient_history_and_speed_above_threshold(self):
        self._set_next_transfer_info_response(download_bytes=0)
        self.inhibitor.does_inhibit()
        sleep(0.030)
        self._set_next_transfer_info_response(download_bytes=4000)
        self.assertTrue(self.inhibitor.does_inhibit())

    def test_does_inhibit_returns_false_when_sufficient_history_and_speed_below_threshold(self):
        self._set_next_transfer_info_response(download_bytes=0)
        self.inhibitor.does_inhibit()
        sleep(0.030)
        self._set_next_transfer_info_response(download_bytes=3000)
        self.assertFalse(self.inhibitor.does_inhibit())

    def test_does_inhibit_returns_false_when_sufficient_history_and_zero_data_transferred(self):
        self._set_next_transfer_info_response(download_bytes=3000)
        self.inhibitor.does_inhibit()
        sleep(0.030)
        self._set_next_transfer_info_response(download_bytes=3000)
        self.assertFalse(self.inhibitor.does_inhibit())

    def test_does_inhibit_maintains_consistent_performance_over_ten_periods(self):
        delta_transfer_b = [0, 1000, 500, 3500, 500, 3000, 2000, 0, 4000, 4500]
        check_period_sec = 0.030
        expected = [True, False, False, True, False, False, False, False, True, True]
        # first two true b/c insufficient data
        # to predict return value calculate transfer based on data over TWO periods because check period
        # is 1/2 of our average window
        session_b = 0
        for i in range(len(delta_transfer_b)):
            session_b += delta_transfer_b[i]
            self._set_next_transfer_info_response(download_bytes=session_b)
            found = self.inhibitor.does_inhibit()
            self.assertEqual(found, expected[i], f"check period # {i}")
            time.sleep(check_period_sec)

    def test_does_inhibit_returns_true_when_data_transferred_decreases(self):
        # indicator of a bittorrent restart
        self._set_next_transfer_info_response(download_bytes=3000)
        self.inhibitor.does_inhibit()
        sleep(0.030)
        self._set_next_transfer_info_response(download_bytes=0)
        self.assertTrue(self.inhibitor.does_inhibit())

    def test_consistent_operation_after_negative_data_rate_event_does_not_inhibit(self):
        self._set_next_transfer_info_response(download_bytes=3000)
        self.inhibitor.does_inhibit()
        sleep(0.030)
        self._set_next_transfer_info_response(download_bytes=0)
        self.inhibitor.does_inhibit()
        sleep(0.030)
        self._set_next_transfer_info_response(download_bytes=3000)
        self.assertFalse(self.inhibitor.does_inhibit())

    def test_consistent_operation_after_negative_data_rate_event_does_inhibit(self):
        self._set_next_transfer_info_response(download_bytes=3000)
        self.inhibitor.does_inhibit()
        sleep(0.030)
        self._set_next_transfer_info_response(download_bytes=0)
        self.inhibitor.does_inhibit()
        sleep(0.030)
        self._set_next_transfer_info_response(download_bytes=4000)
        self.assertTrue(self.inhibitor.does_inhibit())


class TestQbittorrentInhibitorSeedingChannel(TestCase):
    dual_channel_yml = """
    qbittorrent:
        host_url: "http://test:1234"
        username: "test"
        password: "123456789"
        seeding:
            period_min: .0005  # 30 ms
            min_speed_kbps: 10  # 310 bytes / 30 ms
    """

    def setUp(self) -> None:
        config_provider._load_string(self.dual_channel_yml)
        self.template_mock = Mock()
        self.qb_client_patch = patch("plugin.qbittorrent.Client",
                                     return_value=self.template_mock).start()
        self.inhibitor = QbittorrentInhibitor(channel=QbittorrentInhibitor.Channel.SEEDING)

    def tearDown(self) -> None:
        for patch in self.qb_client_patch,:
            patch.stop()

    def _set_next_transfer_info_response(self, download_bytes: int, seed_bytes: int) -> None:
        self.template_mock.transfer_info = lambda: {"dl_info_data": download_bytes, "up_info_data": seed_bytes}

    def test_does_inhibit_returns_true_when_rate_exceeded(self):
        self._set_next_transfer_info_response(download_bytes=0, seed_bytes=0)
        self.inhibitor.does_inhibit()
        sleep(0.030)
        self._set_next_transfer_info_response(download_bytes=0, seed_bytes=315)
        self.assertTrue(self.inhibitor.does_inhibit())

    def test_does_inhibit_returns_false_when_rate_below_threshold(self):
        self._set_next_transfer_info_response(download_bytes=0, seed_bytes=0)
        self.inhibitor.does_inhibit()
        sleep(0.030)
        self._set_next_transfer_info_response(download_bytes=0, seed_bytes=150)
        self.assertFalse(self.inhibitor.does_inhibit())
