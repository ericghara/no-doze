import unittest
import tempfile
from no_doze_client import NoDozeClient
import os.path as path
import os
from concurrent.futures import ThreadPoolExecutor
import time
import json
from common.message.transform import MessageDecoder
from common.message.messages import BindMessage, InhibitMessage
from datetime import datetime, timedelta
from client.inhibiting_condition import InhibitingCondition
from typing import *

class MockInhibitor(InhibitingCondition):

    def __init__(self, period: timedelta=timedelta(milliseconds=10), inhibit: bool=False):
        super().__init__(name=type(self).__name__, period=period)
        self.inhibit = inhibit

    def does_inhibit(self) -> bool:
        return self.inhibit

class TestNoDozeClient(unittest.TestCase):

    REATTEMPT_DELAY = timedelta(milliseconds=1)
    MAX_RECONNECTIONS = 3

    def setUp(self) -> None:
        self.dir = tempfile.TemporaryDirectory(prefix="no_doze_test_")
        self.dir_name = self.dir.name
        self.inhibitor = MockInhibitor()
        self.client = NoDozeClient(base_dir=self.dir_name, max_reconnections=self.MAX_RECONNECTIONS,
                                   retry_delay=self.REATTEMPT_DELAY)
        self.client.add_inhibitor(self.inhibitor)
        self.pool = ThreadPoolExecutor(2)

    def tearDown(self) -> None:
        self.client.close_fifo()
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


    def test_open_fifo_spins_when_no_fifo(self):
        f = self.pool.submit(self.client.open_fifo)
        time.sleep(0.050)
        self.assertFalse(f.done())
        # Just allow thread to join
        self.makeFifo(1)
        f.result()

    def test_open_fifo_spins_when_two_fifos(self):
        extra_fifo = self.makeFifo(1)
        self.makeFifo(2)
        f = self.pool.submit(self.client.open_fifo)
        time.sleep(0.050)
        self.assertFalse(f.done())
        # allow thread to join
        os.unlink(extra_fifo)
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

    def test_close_fifo_causes_client_rebind(self):
        fifo = self.makeFifo(1)
        f = self.pool.submit(self.client.run)
        for i in range(self.MAX_RECONNECTIONS):
            obj = json.loads(self.readFifo(fifo), cls=MessageDecoder)
            self.assertTrue(isinstance(obj, BindMessage))
            self.client.close_fifo()
        f.result(timeout=0.050)


if __name__ == '__main__':
    unittest.main()
