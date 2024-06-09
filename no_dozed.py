import logging
import os
import os.path
from typing import *
from datetime import timedelta
from datetime import datetime
from time import sleep
from os import path
import json
import signal
import glob
import re
import subprocess
from common.message.transform import MessageDecoder
from common.message.messages import InhibitMessage, BindMessage
from server.sleep_inhibitor import SleepInhibitor
import common.config_provider as config_provider
from common.config_provider import CastFn
import argparse

# YAML config keys
LOGGING_LEVEL_KEY = "logging_level"
BASE_DIR_KEY = "base_dir"
POLL_INTERVAL_KEY = "poll_interval_min"
FIFO_PERMISSIONS_KEY = "fifo_permissions"

# Global defaults
DEFAULT_CONFIG_PATH = "./resources/daemon_config.yml"



class Server:

    DEFAULT_BASE_DIR = path.relpath("/")
    DEFAULT_FIFO_PERMISSIONS = 0o666
    DEFAULT_POLL_INTERVAL = timedelta(seconds=10)

    FIFO_BUFFER_B = 4096  # linux default
    FIFO_PREFIX = "FIFO_"
    UNBIND_SIGNAL = signal.SIGUSR1

    WHO = "No-Doze Service"
    WHY = "A monitored process/event is in progress."
    WHAT = "sleep"
    MODE = "block"  # "delay" | "block"

    def __init__(self, base_dir: str = DEFAULT_BASE_DIR, poll_interval: timedelta = DEFAULT_POLL_INTERVAL,
                 permissions: int = DEFAULT_FIFO_PERMISSIONS):
        self._log = logging.getLogger(type(self).__name__)
        self._base_dir = base_dir
        self._fifo_path = path.join(base_dir, f"{self.FIFO_PREFIX}{os.getpid()}")
        self._poll_interval = poll_interval
        self._permissions = permissions
        self._fifo: Optional[IO] = None
        self._bound_client = None # pid of connected client


    def __enter__(self) -> 'Server':
        self._fifo = self._open()

        if self._sleep_inhibitor:
            raise ValueError("Cannot re-open this resource, it is already open.")
        self._sleep_inhibitor = SleepInhibitor(who=self.WHO, why=self.WHY)
        self._sleep_inhibitor.__enter__()

        return self

    def __exit__(self, exc_type: any, exc_val: any, exc_tb: any):
        try:
            self._fifo.close()
        except Exception as e:
            self._log.warning(f"Unable to close fifo {self._fifo_path or '[Unknown]'}", exc_info=e)
        try:
            os.unlink(self._fifo_path)
        except Exception as e:
            self._log.warning(f"Unable to delete fifo {self._fifo_path or '[Unknown]'}", exc_info=e)

        if self._timer:
            self._timer.cancel()
            self._timer = None

        if self._sleep_inhibitor:
            self._sleep_inhibitor.__exit__(exc_type=exc_type, exc_val=exc_val, exc_tb=exc_tb)

        self._sleep_inhibitor = None
        self._bound_client = None
        self._inhibit_until = datetime.now()

    def _open(self) -> IO:
        self._clear_stale_fifos()
        self._log.debug(f"Creating FIFO {self._fifo_path}.")
        os.mkfifo(path=self._fifo_path, mode=self._permissions)
        f = open(self._fifo_path, mode="r+b", buffering=0)
        os.set_blocking(f.fileno(), False)
        return f

    def _clear_stale_fifos(self) -> None:
        """
        Deletes old FIFOs and takes some effort to check if another server instance is actively running.  This is a
        *best effort* attempt and is prone to race conditions.
        :return:
        """
        matcher = re.compile(self.FIFO_PREFIX+r"(\d+)")
        for maybe_fifo in glob.glob(root_dir=self._base_dir, pathname=f"{self.FIFO_PREFIX}*"):
            match = matcher.match(maybe_fifo)
            if match:
                pid = match[1]
                found = subprocess.run(["ps", "p", pid, "o", "cmd", "h"], capture_output=True, text=True)
                if (found.returncode != 0 or pid == os.getpid() or
                        (found.returncode == 0 and not found.stdout.endswith(os.path.basename(__file__)))):
                    # Between restarts cannot rely on PID, so need to check if PID is actually associated with another
                    # server.  Need to handle edge case where a stale FIFO happens to have same PID as current process.
                    stale_fifo_path = os.path.join(self._base_dir, maybe_fifo)
                    self._log.info(f"Deleting stale FIFO: {stale_fifo_path}")
                    os.unlink(stale_fifo_path)
                elif pid == self._bound_client:
                    self._log.info(f"An already bound client: {pid}, sent a bind request.  Allowing.")
                else:
                    self._log.warning(f"Cannot clear stale FIFOs another server appears to be running. PID:{pid}")
                    raise FileExistsError("Another FIFO exists and is in use. Refusing to delete.")

    def _handle_bind(self, msg: BindMessage) -> None:
        if self._bound_client is None:
            self._bound_client = msg.pid
        else:
            self._log.warning(f"Ignoring bind request from a client: {msg.pid}.  "
                              f"Already bound to: {self._bound_client}")
            try:
                self._log.info(f"Sending unbind signal to: {msg.pid}")
                # Send client a (POSIX) signal to unbind.  Eventually it should give up, or potentially
                # user started a new client in preparation to restart this server.
                os.kill(msg.pid, self.UNBIND_SIGNAL)
            except ProcessLookupError as e:
                self._log.warning(f"Unable to send unbind message to: {msg.pid}.  Process went down?")

    def _handle_inhibit(self, msg: InhibitMessage) -> None:
        if msg.pid != self._bound_client:
            self._log.warning(f"Ignoring message from unbound client. Pid: {msg.pid}")
            return

        if self._inhibit_until < msg.expiry_timestamp:
            self._inhibit_until = msg.expiry_timestamp
            self._log.debug(f"Sleep inhibited until: {msg.expiry_timestamp} by {msg.gid}:{msg.pid}.")
        else:
            self._log.debug(f"Received message that does not extend sleep.")

    def _receive_messages(self) -> None:
        while raw_message := self._fifo.readline():
            if len(raw_message) >= self.FIFO_BUFFER_B:
                # fifos have atomic writes up to buffer size (never have atomic reads)
                self._log.warning("Message too long.  Writes not guaranteed atomic.")
            message_json = raw_message.decode().rstrip('\n')
            message = None
            try:
                message = json.loads(message_json, cls=MessageDecoder)
            except Exception as e:
                self._log.warning("Unable to decode message.", exc_info=e)
                continue
            try:
                match type(message):
                    case BindMessage.__class__:
                        self._handle_bind(message)
                    case InhibitMessage.__class__:
                        self._handle_inhibit(message)
                    case _:
                        raise ValueError("Unrecognized message type.")
            except Exception as e:
                self._log.warning("Error while handling a message.", exc_info=e)
                self._log.info(f"Failing message: {message_json}")



    def run(self) -> None:
        while True:
            self._receive_messages()
            sleep_time = self._inhibit_until - datetime.now()
            if sleep_time < timedelta() or sleep_time > self._poll_interval:
                sleep_time = self._poll_interval
            self.set_inhibitor(do_inhibit=self.inhibited())
            sleep(sleep_time.total_seconds())

    def bound_to(self) -> int:
        return self._bound_client

    def inhibited(self) -> bool:
        return self._inhibit_until > datetime.now()

def main() -> None:
    base_dir = config_provider.get_value([BASE_DIR_KEY], "./")
    poll_interval = config_provider.get_value([POLL_INTERVAL_KEY], default=timedelta(minutes=1),
                                              cast_fn=CastFn.to_timedelta_min)
    permissions = config_provider.get_value([FIFO_PERMISSIONS_KEY], default="660",
                                                 cast_fn=CastFn.to_ocatl_int)
    with Server(base_dir=base_dir, poll_interval=poll_interval, permissions=permissions) as server:
        server.run()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="no_dozed",
        description="Sleep inhibition-as-a-service"
    )
    parser.add_argument('-c', '--config', type=str, help="path to config file",
                        default=DEFAULT_CONFIG_PATH)
    args = parser.parse_args()

    config_provider.load_file(args.config)
    logging.basicConfig(level=config_provider.get_value([LOGGING_LEVEL_KEY], "INFO"))
    main()

    # set-up signal handler for graceful shutdown
    # todo switch to blocking read of FIFO?, drop poll interval?
    pass