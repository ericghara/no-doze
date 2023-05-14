import time
from collections import deque
from datetime import datetime, timedelta
from math import inf
from time import sleep
from unittest import TestCase
from unittest.mock import Mock, patch
from src import config_provider

from src.trigger.implementations.qbittorrent import TimeBytes, QbittorrentInhibitor

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
        self.qb_client_patch = patch("src.trigger.implementations.qbittorrent.Client", return_value=self.template_mock).start()
        self.inhibitor = QbittorrentInhibitor()

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
        self.assertTrue(self.inhibitor.does_inhibit() )

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
        delta_transfer_b = [0, 1000, 500, 2000, 500, 3000, 2000, 0, 4000, 4500]
        check_period_sec = 0.015 # note this is the global period, i.e. frequency does_inhibit is polled
        expected = [True, True, False, False, False, True, True, False, True, True]
        # first two true b/c insufficient data
        # to predict return value calculate transfer based on data over TWO periods because check period
        # is 1/2 of our average window
        session_b = 0
        for i in range(len(delta_transfer_b) ):
            session_b += delta_transfer_b[i]
            self._set_next_transfer_info_response(download_bytes=session_b)
            found = self.inhibitor.does_inhibit()
            self.assertEquals(found, expected[i], f"check period # {i}")
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

    ## These tests are redundant, but provide good documentation for how things work
    def test__calc_mean_kbps_in_window_normal_operation(self):
        # normal operation is window monotonically increasing on time and
        # monotonically non-decreasing on bytes
        now = datetime.now()
        period = timedelta(seconds=0.5)
        window = deque([TimeBytes(time=now, bytes=1024),
                        TimeBytes(time=now - period, bytes=0)])
        found_kbps = self.inhibitor._calc_mean_kbps_in_window(history=window, period=period)
        self.assertEqual(2, found_kbps)

    def test__calc_mean_kbps_in_window_stalled_transfer(self):
        now = datetime.now()
        period = timedelta(seconds=0.5)
        window = deque([TimeBytes(time=now, bytes=1024),
                        TimeBytes(time=now - period, bytes=1024)])
        found_kbps = self.inhibitor._calc_mean_kbps_in_window(history=window, period=period)
        self.assertEqual(0, found_kbps)

    def test__calc_mean_kbps_in_window_returns_inf_when_single_datapoint(self):
        now = datetime.now()
        period = timedelta(seconds=0.5)
        window = deque([TimeBytes(time=now, bytes=1024)])
        found_kbps = self.inhibitor._calc_mean_kbps_in_window(history=window, period=period)
        self.assertEqual(inf, found_kbps)

    def test__calc_mean_kbps_in_window_returns_inf_when_insufficient_history(self):
        # normal operation is window monotonically increasing on time and
        # monotonically non-decreasing on bytes
        now = datetime.now()
        period = timedelta(seconds=0.5)
        window = deque([TimeBytes(time=now, bytes=1024),
                        TimeBytes(time=now - period/2, bytes=0)])
        found_kbps = self.inhibitor._calc_mean_kbps_in_window(history=window, period=period)
        self.assertEqual(inf, found_kbps)

    def test__calc_mean_kbps_in_window_returns_inf_when_bytes_decrease(self):
        now = datetime.now()
        period = timedelta(seconds=0.5)
        window = deque([TimeBytes(time=now, bytes=512),
                        TimeBytes(time=now - period, bytes=1024)])
        self.assertEqual(inf, self.inhibitor._calc_mean_kbps_in_window(history=window, period=period))

    ## End redundant tests

class TestQbittorrentInhibitorDualChannel(TestCase):

    dual_channel_yml = """
    qbittorrent:
        host_url: "http://test:1234"
        username: "test"
        password: "123456789"
        downloading:
            period_min: .0005  # 30 ms
            min_speed_kbps: 100  # 3072 bytes / 30 ms
        seeding:
            period_min: .0005  # 30 ms
            min_speed_kbps: 10  # 310 bytes / 30 ms 
    """


    def setUp(self) -> None:
        config_provider._load_string(self.dual_channel_yml)
        self.template_mock = Mock()
        self.qb_client_patch = patch("src.trigger.implementations.qbittorrent.Client", return_value=self.template_mock).start()
        self.inhibitor = QbittorrentInhibitor()

    def tearDown(self) -> None:
        for patch in self.qb_client_patch,:
            patch.stop()


    def _set_next_transfer_info_response(self, download_bytes: int, seed_bytes: int) -> None:
        self.template_mock.transfer_info = lambda: {"dl_info_data": download_bytes, "up_info_data": seed_bytes}

    def test_does_inhibit_returns_true_when_only_seed_inhibits(self):
        self._set_next_transfer_info_response(download_bytes=0, seed_bytes=0)
        self.inhibitor.does_inhibit()
        sleep(0.030)
        self._set_next_transfer_info_response(download_bytes=310, seed_bytes=310)
        self.assertTrue(self.inhibitor.does_inhibit() )

    def test_does_inhibit_returns_false_when_neither_seed_nor_download_inhibits(self):
        self._set_next_transfer_info_response(download_bytes=0, seed_bytes=0)
        self.inhibitor.does_inhibit()
        sleep(0.030)
        self._set_next_transfer_info_response(download_bytes=155, seed_bytes=155)
        self.assertFalse(self.inhibitor.does_inhibit())
