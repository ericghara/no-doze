import unittest
from datetime import timedelta, datetime
from unittest.mock import patch, MagicMock

from core import config_provider as config_provider
from no_doze import NoDoze, ScheduledCheck
from test.plugin.test_condtions import ProgrammableInhibitor


class NoDozeTest(unittest.TestCase):

    def setUp(self):
        self.sleep_inhibitor_mock = MagicMock()
        self.sleep_inhibitor_mock.__enter__.return_value = self.sleep_inhibitor_mock

        self.sleep_inhibitor_patch = patch('no_doze.SleepInhibitor', return_value=self.sleep_inhibitor_mock).start()
        config_provider._load_string("""
        startup_delay_min: 0
        logging_level: "DEBUG"
        """)
        self.no_doze = NoDoze()
        self.period = timedelta(seconds=0.030)  # 30 ms
        self.process_stub = ProgrammableInhibitor(period=self.period)
        self.no_doze.add_inhibitor(self.process_stub)

    def tearDown(self) -> None:
        unittest.mock.patch.stopall()

    def test_add_inhibitor_adds_to_inhibiting_processes(self):
        self.assertEqual(self.no_doze.inhibiting_processes, [self.process_stub], "Inhibiting conditions")

    def test_add_inhibitor_adds_to_schedule(self):
        self.assertEqual(1, len(self.no_doze._schedule), "length")
        item: ScheduledCheck = self.no_doze._schedule.peek()
        self.assertEqual(item.inhibiting_process, self.process_stub, "expected inhibitor")
        self.assertTrue(datetime.now() >= item.time and item.time + timedelta(milliseconds=10) > datetime.now(),
                        "Expected time")

    def test_exit_closes_sleep_inhibitor_resource(self):
        with self.no_doze:
            print(self.no_doze._sleep_inhibitor == self.sleep_inhibitor_mock)
        self.sleep_inhibitor_mock.__exit__.assert_called_once()

    def test_handle_scheduled_checks_does_not_poll_before_scheduled_time(self):
        with patch('no_doze.datetime') as date_mock:
            date_mock.now.return_value = datetime.min
            self.no_doze._handle_scheduled_checks()
            self.assertFalse(self.process_stub.was_called())

    def test_handle_scheduled_checks_polls_at_scheduled_time(self):
        self.process_stub.set_next(True)
        self.no_doze._handle_scheduled_checks()
        self.assertTrue(self.process_stub.was_called())

    def test_handle_scheduled_schedules_one_period_in_future(self):
        self.process_stub.set_next(True)
        first_time = self.no_doze._schedule.peek().time
        self.no_doze._handle_scheduled_checks()
        second_time = self.no_doze._schedule.peek().time
        self.assertEqual(first_time + self.period, second_time, "next scheduled check is at the expected time")

    def test_no_doze_calls_inhibit_sleep_inhibition_required_and_there_is_no_ongoing_inhibition(self):
        with self.no_doze:
            self.sleep_inhibitor_mock.is_inhibiting.return_value = False
            self.process_stub.set_next(True)
            self.no_doze._handle_period()
        self.sleep_inhibitor_mock.inhibit_sleep.assert_called_once()
        self.sleep_inhibitor_mock.allow_sleep.assert_not_called()

    def test_no_doze_does_not_call_inhibit_sleep_when_inhibition_required_and_there_is_ongoing_inhibition(self):
        with self.no_doze:
            self.sleep_inhibitor_mock.is_inhibiting.return_value = True
            self.process_stub.set_next(True)
            self.no_doze._handle_period()
        self.sleep_inhibitor_mock.inhibit_sleep.assert_not_called()
        self.sleep_inhibitor_mock.allow_sleep.assert_not_called()

    def test_no_doze_does_not_call_allow_sleep_or_inhibit_sleep_when_no_sleep_required_and_no_inhibition_ongoing(self):
        with self.no_doze:
            self.sleep_inhibitor_mock.is_inhibiting.return_value = False
            self.process_stub.set_next(False)
            self.no_doze._handle_period()
        self.sleep_inhibitor_mock.inhibit_sleep.assert_not_called()
        self.sleep_inhibitor_mock.allow_sleep.assert_not_called()

    def test_no_doze_does_call_allow_sleep_when_no_sleep_required_and_inhibition_ongoing(self):
        with self.no_doze:
            self.sleep_inhibitor_mock.is_inhibiting.return_value = True
            self.process_stub.set_next(False)
            self.no_doze._handle_period()
        self.sleep_inhibitor_mock.inhibit_sleep.assert_not_called()
        self.sleep_inhibitor_mock.allow_sleep.assert_called_once()
