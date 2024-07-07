import threading
import unittest
from datetime import timedelta, datetime
from time import sleep
from typing import *
from unittest.mock import Mock

from jeepney.low_level import Message

from server.sleep_watcher import SleepWatcher


class TestSleepWatcher (unittest.TestCase):

    """
    These tests are a bit trivial
    """

    def setUp(self):
        self.n_prepare_callbacks = 0
        self.n_awake_callbacks = 0

        def prepare_callback():
            self.n_prepare_callbacks += 1

        def awake_callback():
            self.n_awake_callbacks += 1
        self.watcher = SleepWatcher(before_sleep_callback=prepare_callback,
                                    awake_callback=awake_callback)
        self.watcher.__enter__()

    def tearDown(self):
        self.watcher.__exit__(None, None, None)

    def run_mocked(self, messages: List[bool], timeout:timedelta=timedelta(milliseconds=250)):
        """
        :param messages: list of true/false PrepareForSleep messages
        :return: Sleep watcher with messages injected
        """
        def mock_message(is_prepare_for_sleep: bool) -> Message:
            msg_mock = Mock()
            msg_mock.body = [is_prepare_for_sleep]
            return msg_mock

        signals = [mock_message(val) for val in messages]
        threading.Thread(target=lambda: self.watcher.run(mock_signals=signals),
                         daemon=True).start()

        deadline = datetime.now() + timeout
        while self.n_awake_callbacks + self.n_prepare_callbacks < len(signals) and datetime.now() < deadline:
            sleep(0.005)


    def test_calls_before_sleep_callback_on_prepare_for_sleep_message(self):
        self.run_mocked(messages=[True])
        self.assertEqual(1, self.n_prepare_callbacks)
        self.assertEqual(0, self.n_awake_callbacks)

    def test_calls_awake_callback_on_awake_from_sleep_message(self):
        self.run_mocked(messages=[False])
        self.assertEqual(0, self.n_prepare_callbacks)
        self.assertEqual(1, self.n_awake_callbacks)


