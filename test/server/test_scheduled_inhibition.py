import unittest
from datetime import timedelta, datetime

from server.scheduled_inhibition import ScheduledInhibition


class TestScheduledInhibition(unittest.TestCase):

    # Note this will actually schedule sleep inhibitions, but if run as a non-privileged user should have
    # no actual effect.
    def setUp(self) -> None:
        self.sched = ScheduledInhibition(who="test", why="test").__enter__()
        self.inhib = self.sched._sleep_inhibitor  # just a convenient handle, owned by ScheduledInhibitor

    def tearDown(self) -> None:
        self.sched.__exit__(None, None, None)

    def get_sleep_duration(self, timeout=timedelta(milliseconds=50)) -> timedelta:
        start = datetime.now()
        deadline = start+timeout
        inSleep = 0
        while inSleep < 2 and datetime.now() < deadline:
            if self.inhib.is_inhibiting():
                inSleep = 1
            elif inSleep == 1:
                inSleep = 2

        return datetime.now()-start

    def test_set_inhibitor_new_sleep_enters_exits_sleep(self):
        expected_duration = timedelta(milliseconds=50)
        until = datetime.now() + expected_duration
        self.sched.set_inhibitor(until=until)
        duration = self.get_sleep_duration(timeout=timedelta(milliseconds=100))
        self.assertTrue(expected_duration * 0.8 < duration, f"sleep too short {duration}")
        self.assertTrue(expected_duration * 1.2 > duration, f"sleep too long {duration}")

    def test_set_inhibitor_extends_existing_sleep(self):
        until0 = datetime.now() + timedelta(milliseconds=50)
        expectedDuration = timedelta(milliseconds=100)
        until1 = datetime.now() + expectedDuration
        self.sched.set_inhibitor(until=until0)
        self.sched.set_inhibitor(until=until1)
        duration = self.get_sleep_duration(timeout=timedelta(milliseconds=150))
        self.assertTrue(expectedDuration * .8 < duration, f"sleep too short {duration}")
        self.assertTrue(expectedDuration * 1.2 > duration, f"sleep too long {duration}")

    def test_set_inhibitor_in_past_immediately_returns_false(self):
        until = datetime.now()-timedelta(milliseconds=1)
        foundRet = self.sched.set_inhibitor(until=until)
        timeout = timedelta(milliseconds=25)
        foundDuration = self.get_sleep_duration(timeout=timeout) # expect timeout
        self.assertFalse(foundRet, "return value")
        self.assertGreaterEqual(foundDuration, timeout, "expect timeout, never inhibited")

    def test_set_inhibitor_in_past_no_effect_on_existing_sleep(self):
        expected_duration = timedelta(milliseconds=50)
        until0 = datetime.now() + expected_duration
        until1 = datetime.now() - timedelta(milliseconds=25)
        timeout = timedelta(milliseconds=75)
        self.sched.set_inhibitor(until0)
        foundRet = self.sched.set_inhibitor(until1)
        foundDuration = self.get_sleep_duration(timeout=timeout)
        self.assertFalse(foundRet, "return value")
        self.assertLess(expected_duration * .75, foundDuration, f"inhibition too short {foundDuration}")
        self.assertGreater(expected_duration * 1.25, foundDuration, f"inhibition too long {foundDuration}")

    def test_set_inhibitor_does_not_clear_sleep_when_cancellation_race(self):
        # case where a new inhibition scheduled *just* as one is expiring
        # earlier inhibition callback fires to try to stop inhibition,
        # sees new period has begun and does nothing.
        until0 = datetime.now() + timedelta(milliseconds=50)
        until1 = until0 + timedelta(microseconds=1)
        timeout = timedelta(milliseconds=75)
        self.sched.set_inhibitor(until0)
        self.sched._inhibit_until = until1 # simulate a race
        foundDuration = self.get_sleep_duration(timeout=timeout)
        self.assertGreaterEqual(foundDuration, timeout)

    def test_set_inhibitor_returns_false_when_not_open(self):
        self.sched.__exit__(None, None, None)
        until = datetime.now() + timedelta(milliseconds=50)
        self.assertFalse(self.sched.set_inhibitor(until))






