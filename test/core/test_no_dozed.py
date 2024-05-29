import unittest
import tempfile
import os
import os.path as path

import core.server.no_dozed
from core.server.no_dozed import Server, FIFO_PREFIX


class TestNoDozeD(unittest.TestCase):

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory(prefix="no_doze_test_")
        self.dir_name = self.dir.name
        self.server = Server(base_dir=self.dir_name)

    def tearDown(self):
        if self.dir:
            self.dir.cleanup()
    def test__clear_stale_fifos_no_process_do_delete(self):
        dummy_fifo = path.join(self.dir_name, f"{FIFO_PREFIX}32768")
        with open(dummy_fifo, "w") as f:
            pass
        self.server._clear_stale_fifos()
        self.assertFalse(os.path.exists(dummy_fifo))

    def test_clear_stale_fifos_weird_name_no_delete(self):
        dummy_fifo = path.join(self.dir_name, f"{FIFO_PREFIX}not_a_pid")
        with open(dummy_fifo, "w") as f:
            pass
        self.server._clear_stale_fifos()
        self.assertTrue(os.path.exists(dummy_fifo))

    def test_clear_stale_fifos_pid_found_no_cmd_name_match_delete(self):
        dummy_fifo = path.join(self.dir_name, f"{FIFO_PREFIX}{os.getpid()}")
        with open(dummy_fifo, "w") as f:
            pass
        self.server._clear_stale_fifos()
        self.assertFalse(os.path.exists(dummy_fifo))

    def test_with_creates_and_deletes_fifo(self):
        with self.server as s:
            self.assertTrue(os.path.exists(self.server.fifo_path))
        self.assertFalse(os.path.exists(self.server.fifo_path))

if __name__ == '__main__':
    unittest.main()
