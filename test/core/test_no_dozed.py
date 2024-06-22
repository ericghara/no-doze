import signal
import unittest
import tempfile
import os
import os.path as path
import json
from common.message.messages import BindMessage, InhibitMessage
from common.message.transform import MessageEncoder
from datetime import datetime, timedelta
from threading import Timer
import time

from no_dozed import Server
from typing import Any


class TestNoDozeD(unittest.TestCase):

    # These tests will try to inhibit sleep on the system they are running on,
    # however these changes should have little effect when run *unprivileged*.

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory(prefix="no_doze_test_")
        self.dir_name = self.dir.name
        self.server = Server(base_dir=self.dir_name)
        self.server.__enter__()

    def tearDown(self):
        if self.dir:
            self.dir.cleanup()
        self.server.__exit__(None, None, None)

    def send_message(self, obj: Any, fifo: str) -> None:
        payload = json.dumps(obj, cls=MessageEncoder) + "\n"
        with open(fifo, "w+b", buffering=0) as w_fifo:
            w_fifo.write(payload.encode())
        return

    def test__clear_stale_fifos_no_process_do_delete(self):
        dummy_fifo = path.join(self.dir_name, f"{self.server.FIFO_PREFIX}32768")
        with open(dummy_fifo, "w") as f:
            pass
        self.server._clear_stale_fifos()
        self.assertFalse(os.path.exists(dummy_fifo))

    def test_clear_stale_fifos_weird_name_no_delete(self):
        dummy_fifo = path.join(self.dir_name, f"{self.server.FIFO_PREFIX}not_a_pid")
        with open(dummy_fifo, "w") as f:
            pass
        self.server._clear_stale_fifos()
        self.assertTrue(os.path.exists(dummy_fifo))

    def test_clear_stale_fifos_pid_found_no_cmd_name_match_delete(self):
        dummy_fifo = path.join(self.dir_name, f"{self.server.FIFO_PREFIX}{os.getpid()}")
        with open(dummy_fifo, "w") as f:
            pass
        self.server._clear_stale_fifos()
        self.assertFalse(os.path.exists(dummy_fifo))

    def test_with_creates_and_deletes_fifo(self):
        self.assertTrue(os.path.exists(self.server._fifo_path))
        self.server.__exit__(None, None, None)
        self.assertFalse(os.path.exists(self.server._fifo_path))

    def test__binds_when_unbound(self):
        msg = BindMessage(pid=123, uid=567, attempt=0)
        self.server._handle_bind(msg)
        self.assertEqual({msg.pid}, self.server.bound_to())

    def test__does_not_rebind(self):
        expected = {123, 321}
        for pid in expected:
            # currently same uid can bind multiple times
            msg = BindMessage(pid=pid, uid=567, attempt=0)
            self.server._handle_bind(msg)
        self.assertEqual(expected, self.server.bound_to())

    def test__handle_inhibit_ignores_unbound(self):
        msg = InhibitMessage(pid=123, uid=567, expiry_timestamp=datetime.now() + timedelta(seconds=100))
        self.server._handle_inhibit(msg)
        self.assertFalse(self.server.inhibited())

    def test__handle_inhibit_updates_expiry_in_future(self):
        bind_message = BindMessage(pid=123, uid=567, attempt=0)
        self.server._handle_bind(bind_message)
        inhibit_msg = InhibitMessage(pid=123, uid=567, expiry_timestamp=datetime.now() + timedelta(seconds=100))
        self.server._handle_inhibit(inhibit_msg)
        self.assertTrue(self.server.inhibited())

    def test__handle_inhibit_does_not_update_expiry_in_past(self):
        bind_message = BindMessage(pid=123, uid=567, attempt=0)
        self.server._handle_bind(bind_message)
        inhibit_msg = InhibitMessage(pid=123, uid=567, expiry_timestamp=datetime.now() + timedelta(seconds=100))
        self.server._handle_inhibit(inhibit_msg)
        inhibit_msg2 = InhibitMessage(pid=123, uid=567, expiry_timestamp=datetime.now() + timedelta(seconds=-10))
        self.server._handle_inhibit(inhibit_msg2)
        self.assertTrue(self.server.inhibited())

    def test__handle_inhibit_updates_on_further_in_future_expiry(self):
        bind_message = BindMessage(pid=123, uid=567, attempt=0)
        self.server._handle_bind(bind_message)
        inhibit_msg = InhibitMessage(pid=123, uid=567, expiry_timestamp=datetime.now() + timedelta(milliseconds=50))
        self.server._handle_inhibit(inhibit_msg)
        inhibit_msg2 = InhibitMessage(pid=123, uid=567, expiry_timestamp=datetime.now() + timedelta(seconds=10))
        self.server._handle_inhibit(inhibit_msg2)
        time.sleep(55/1000)
        self.assertTrue(self.server.inhibited())

    def test__run_stops_when_catches_a_shutdown_signal(self):
        t_fail = Timer(1.0, lambda: self.fail("Server hung, did not shut-down"))
        t_fail.start()
        for sig in signal.SIGINT, signal.SIGTERM, signal.SIGHUP, signal.SIGQUIT:
            t = Timer(0.030, lambda: os.kill(os.getpid(), signal.SIGINT))
            t.start()
            self.server.run()


if __name__ == '__main__':
    unittest.main()
