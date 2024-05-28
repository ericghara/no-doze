import logging
import os
import os.path
import stat
from typing import *
from datetime import timedelta
from datetime import datetime
from time import sleep
import random
from os import path
import glob
import re
import subprocess

DEFAULT_FIFO_DIR = path.relpath("../../")
FIFO_PREFIX = "FIFO_"
DEFAULT_PERMISSIONS = 0o666
DEFAULT_POLL_INTERVAL = timedelta(seconds=1)


class Server:

    def __init__(self, base_dir: str = DEFAULT_FIFO_DIR, poll_interval: timedelta = DEFAULT_POLL_INTERVAL,
                 permissions: int = DEFAULT_PERMISSIONS):
        self._log = logging.getLogger(type(self).__name__)
        self.base_dir = base_dir
        self.fifo_path = path.join(base_dir, f"{FIFO_PREFIX}{os.getpid()}")
        self.poll_interval = poll_interval
        self.permissions = permissions
        self.fifo = None
        self.bound_client = None # pid of connected client

    def __enter__(self) -> 'Server':
        self.fifo = self._open()
        return self

    def __exit__(self, exec_type: any, exec_val: any, exec_tb: any):
        try:
            self.fifo.close()
        except Exception as e:
            self._log.warning(f"Unable to close fifo {self.fifo_path or '[Unknown]'}", exc_info=e)
        try:
            os.unlink(self.fifo_path)
        except Exception as e:
            self._log.warning(f"Unable to delete fifo {self.fifo_path or '[Unknown]'}", exc_info=e)

    def _clear_stale_fifos(self) -> None:
        matcher = re.compile(FIFO_PREFIX+r"(\d+)")
        for maybe_fifo in glob.glob(root_dir=self.base_dir, pathname=f"{FIFO_PREFIX}*"):
            match = matcher.match(maybe_fifo)
            if match:
                pid = match[1]
                found = subprocess.run(["ps", "p", pid, "o", "cmd", "h"], capture_output=True, text=True)
                if (found.returncode != 0 or
                        (found.returncode == 0 and not found.stdout.endswith(os.path.basename(__file__)))):
                    # between restarts cannot rely on PID, so checking to make sure PID isn't associated with another
                    # server
                    stale_fifo_path = os.path.join(self.base_dir, maybe_fifo)
                    self._log.info(f"Deleting stale FIFO: {stale_fifo_path}")
                    os.unlink(stale_fifo_path)
                else:
                    self._log.warning(f"Cannot clear stale FIFOs another server appears to be running. PID:{pid}")
                    raise FileExistsError("Another FIFO exists and is in use. Refusing to delete.")


    def _open(self) -> IO:
        self._clear_stale_fifos()
        self._log.debug(f"Creating FIFO {self.fifo_path}.")
        os.mkfifo(path=self.fifo_path, mode=self.permissions)
        return open(self.fifo_path, mode="r+b", buffering=0)


if __name__ == "__main__":
    pass