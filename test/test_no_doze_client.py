import json
import logging
import os
import os.path as path
import signal
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from typing import *

from client.inhibiting_condition import InhibitingCondition
from common.message.messages import BindMessage, InhibitMessage
from common.message.transform import MessageDecoder
from no_doze_client import NoDozeClient


class MockInhibitor(InhibitingCondition):

    def __init__(self, period: timedelta=timedelta(milliseconds=10), inhibit: bool=False):
        super().__init__(name=type(self).__name__, period=period)
        self.inhibit = inhibit
        self.num_calls = 0

    def does_inhibit(self) -> bool:
        self.num_calls += 1
        return self.inhibit

class TestNoDozeClient(unittest.TestCase):

    REATTEMPT_DELAY = timedelta(milliseconds=1)
    MAX_RECONNECTIONS = 3

    def setUp(self) -> None:
        logging.basicConfig(level="DEBUG")
        self.dir = tempfile.TemporaryDirectory(prefix="no_doze_test_")
        self.dir_name = self.dir.name
        self.inhibitor = MockInhibitor()
        self.client = NoDozeClient(base_dir=self.dir_name, retry_delay=self.REATTEMPT_DELAY)
        self.client.add_inhibitor(self.inhibitor)
        self.client.__enter__()
        self.pool = ThreadPoolExecutor(2)

    def tearDown(self) -> None:
        self.client.__exit__(None, None, None)

        if self.dir:
            self.dir.cleanup()
        if self.pool:
            self.pool.shutdown(wait=False, cancel_futures=True)


    def makeFifo(self, pid: int) -> path:
        fifo_path = path.join(self.dir_name, self.client.FIFO_PREFIX + str(pid))
        os.mkfifo(fifo_path, mode=0o666)
        return fifo_path

    def readFifo(self, fifo_path: path, timeout: timedelta=timedelta(milliseconds=100)) -> Optional[str]:
        timeout = datetime.now() + timeout
        with open(fifo_path, "r+b", buffering=0) as f:
            os.set_blocking(f.fileno(), False)
            while datetime.now() < timeout:
                try:
                    line = f.readline()
                    if line:
                        return line.decode().rstrip('/n')
                except:
                    pass
        return None


    def send_signal_to_client(self, sig: int) -> None:
        if sig < 0 or sig > 255:
            raise ValueError("out of range")
        os.write(self.client._sig_w_fd, chr(sig).encode('ascii'))

    def test_client_responds_to_shutdown_signals_when_no_fifo(self):
        f = self.pool.submit(self.client.run)
        self.send_signal_to_client(signal.SIGTERM)
        time.sleep(0.050)
        self.assertTrue(f.done())
        f.result()

    def test_client_responds_to_shutdown_signals_when_fifo(self):
        f = self.pool.submit(self.client.run)
        fifo = self.makeFifo(1)
        self.assertIsNotNone(self.readFifo(fifo))
        self.send_signal_to_client(signal.SIGTERM)
        time.sleep(0.050)
        self.assertTrue(f.done())
        f.result()

    def test_client_does_not_check_inhibiting_conditions_when_no_fifo(self):
        f = self.pool.submit(self.client.run)
        time.sleep(0.050)
        self.send_signal_to_client(signal.SIGTERM)
        time.sleep(0.050)
        self.assertTrue(f.done())
        self.assertEqual(0, self.inhibitor.num_calls)
        f.result()

    def test_client_does_not_connect_when_two_fifos(self):
        fifo0 = self.makeFifo(1)
        fifo1 = self.makeFifo(2)
        f = self.pool.submit(self.client.run)
        time.sleep(0.050)
        self.assertIsNone(self.readFifo(fifo0, timeout=timedelta(milliseconds=10)))
        self.assertIsNone(self.readFifo(fifo1, timeout=timedelta(milliseconds=10)))
        self.send_signal_to_client(signal.SIGTERM)
        time.sleep(0.050)
        self.assertTrue(f.done())
        f.result()

    def test_open_fifo_sends_bind_message(self):
        fifo = self.makeFifo(1)
        f = self.pool.submit(self.client.open_fifo)
        obj = json.loads(self.readFifo(fifo), cls=MessageDecoder)
        self.assertTrue(isinstance(obj, BindMessage))

    def test_client_sends_inhibit_message(self):
        self.inhibitor.inhibit = True
        fifo = self.makeFifo(1)
        f = self.pool.submit(self.client.run)
        self.readFifo(fifo) # ignore bind message
        obj = json.loads(self.readFifo(fifo), cls=MessageDecoder)
        self.assertTrue(isinstance(obj, InhibitMessage))
        self.client.stop()
        f.result()

    def test_client_does_not_send_inhibit_message_when_no_inhibition(self):
        fifo = self.makeFifo(1)
        f = self.pool.submit(self.client.run)
        self.readFifo(fifo) # ignore bind message
        msg = self.readFifo(fifo)
        self.assertIsNone(msg)
        self.client.stop()
        f.result()

    def test_unbind_signal_causes_client_rebind(self):
        fifo = self.makeFifo(1)
        f = self.pool.submit(self.client.run)
        for i in range(3):
            obj = json.loads(self.readFifo(fifo), cls=MessageDecoder)
            self.assertTrue(isinstance(obj, BindMessage))
            self.send_signal_to_client(self.client.UNBIND_SIGNAL)
        self.client.stop()
        f.result()

    def test_prepare_for_sleep_signal_causes_client_to_check_inhibitor(self):
        fifo = self.makeFifo(1)
        f = self.pool.submit(self.client.run)
        start = datetime.now()
        self.readFifo(fifo) # wait for bind
        # just spam client with about to sleeps
        for _ in range(10):
            self.send_signal_to_client(self.client.ABOUT_TO_SLEEP_SIGNAL)
        time.sleep((timedelta(milliseconds=50)-(datetime.now()-start)).total_seconds())
        # assert we checked far more times than would be expected on normal schedule
        self.assertGreater(self.inhibitor.num_calls, 10)
        self.client.stop()
        f.result()



    def test_client_calls_at_inhibitor_around_scheduled_time(self):
        self.inhibitor.inhibit = True
        fifo = self.makeFifo(1)
        f = self.pool.submit(self.client.run)
        self.readFifo(fifo) # ignore bind message
        stop = datetime.now() + timedelta(milliseconds=100)
        # inhibitor timedelta set to 10 ms
        acc = timedelta()
        cnt = 10
        last = datetime.now()
        for _ in range(10):
            cur = json.loads(self.readFifo(fifo), cls=MessageDecoder).expiry_timestamp
            acc += cur - last
            last = cur
        self.assertTrue(self.inhibitor.period()*0.9 <= acc/cnt <= self.inhibitor.period()*1.1,
                        "Average period")
        self.client.stop()
        f.result(timeout=0.050)

    def test_client_multiple_inhibitors_sends_later_inhibit_time(self):
        long_inhibitor = MockInhibitor(period=timedelta(milliseconds=50), inhibit=True)
        self.inhibitor.inhibit = True # short inhibitor
        self.client.add_inhibitor(long_inhibitor)
        fifo = self.makeFifo(1)
        f = self.pool.submit(self.client.run)
        self.readFifo(fifo) # ignore bind message
        start = datetime.now()
        stop = json.loads(self.readFifo(fifo), cls=MessageDecoder).expiry_timestamp
        self.client.stop()
        self.assertTrue(timedelta(milliseconds=40) < stop-start < timedelta(milliseconds=65))
        f.result(timeout=0.100)

    def test_client_no_message_when_already_inhibiting(self):
        long_inhibitor = MockInhibitor(period=timedelta(milliseconds=50), inhibit=True)
        self.client.add_inhibitor(long_inhibitor)
        fifo = self.makeFifo(1)
        self.client._log.info(datetime.now())
        f = self.pool.submit(self.client.run)
        self.readFifo(fifo)  # ignore bind message
        self.assertIsNotNone(self.readFifo(fifo, timedelta(milliseconds=20)))
        self.inhibitor.inhibit = True  # short inhibitor
        self.assertIsNone(self.readFifo(fifo, timedelta(milliseconds=20)))
        self.client.stop()
        f.result(timeout=0.100)






if __name__ == '__main__':
    unittest.main()
