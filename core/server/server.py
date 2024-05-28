import logging
import os
import os.path
import stat
from typing import *
from datetime import timedelta
from datetime import datetime
from time import sleep
import random

DEFAULT_FIFO_PATH = "../../FIFO"
DEFAULT_PERMISSIONS = 0o666
DEFAULT_POLL_INTERVAL = timedelta(seconds=1)


class Server:

    def __init__(self, fifo_path: str = DEFAULT_FIFO_PATH, poll_interval: timedelta = DEFAULT_POLL_INTERVAL,
                 permissions: int = DEFAULT_PERMISSIONS):
        self._log = logging.getLogger(type(self).__name__)
        self.fifo_path = fifo_path
        self.poll_interval = poll_interval
        self.permissions = permissions
        self.fifo = None

    def __enter__(self) -> 'Server':
        self._open()
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


    def _open(self) -> IO:
        period_slack = self.poll_interval * 1.5
        try:
            st = os.stat(self.fifo_path)
            if not stat.S_ISFIFO(st.st_mode):
                self._log.warning(f"{self.fifo_path} exists and has file mode: {hex(st.st_mode)}.")
                raise FileExistsError(f"{self.fifo_path} exists but is NOT a FIFO.")

            mtime = datetime.fromtimestamp(st.st_mtime + st.st_mtime_ns / 1_000_000_000)
            # mtime used to *infer* if another server is active.
            # This system is not perfect and is prone to races. These edge cases seem acceptable for a daemon.
            if mtime + period_slack < datetime.now():
                self._log.info(f"Deleting FIFO: {self.fifo}.  Appears to be abandoned. Prior unclean shutdown?")
                os.unlink(self.fifo)
            else:
                self._log.info("A potentially active server was detected.  Waiting to infer if is still active.")
                sleep(period_slack * random.uniform(1.0, 1.25))
                st2 = os.stat(self.fifo_path)
                if datetime.fromtimestamp(st2.st_mtime + st2.st_mtime_ns/1_000_000_000) <= mtime:
                    self._log.info(f"Deleting FIFO: {self.fifo}.  Appears to be abandoned. Prior unclean shutdown?")
                    os.unlink(self.fifo)
                else:
                    self._log.warning(f"Another active server was detected using the FIFO.")
                    raise FileExistsError(f"{self.fifo_path} exists and is actively in use.")
        except FileNotFoundError:
            # likely clean shutdown of last server and no other server actively running
            # this is the hapy path
            pass
        except Exception as e:
            raise RuntimeError(f"Error while opening FIFO.", e)

        self._log.debug(f"Creating FIFO {self.fifo_path}.")
        os.mkfifo(path=self.fifo_path, mode=self.permissions)
        return open(self.fifo_path, mode="rb")


if __name__ == "__main__":
    pass