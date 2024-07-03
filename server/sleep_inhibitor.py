import logging
from typing import Optional

import jeepney as jeep
import jeepney.io.blocking as jeep_io

import server.org_freedesktop_login1 as login1_msggen


class SleepInhibitor:

    """
    An API that allows blocking of system sleep.  **Must** be run with root privileges.  Blocking may be indefinite,
    and can only be overridden by a process or user with root privileges.

    In order to ensure orderly freeing of system resources this should be only used in a with statement.

    It is useful to refer to the `systemd-inhibit` man page as well as the
    [systemd-logind Manager Object](https://www.freedesktop.org/software/systemd/man/org.freedesktop.login1.html)
    documentation to better understand how login1 handles sleep.
    """

    _LOGIND_BUS_NAME = 'org.freedesktop.login1'
    _LOGIND_OBJECT_PATH = '/org/freedesktop/login1'
    _LOGIND_MANAGER_INTERFACE = 'org.freedesktop.login1.Manager'
    # time limits exist for delay modes.  Block mode requires root privilege
    _INHIBIT_WHAT = "sleep"

    def __init__(self, who: str, why: str, mode: str = 'block'):
        """

        :param who: Process requesting sleep to be blocked/delayed
        :param why: Reason sleep is being blocked/delayed
        :param mode: 'block' or 'delay', delay will prevent sleep for a few seconds block can delay sleep
        indefinitely (if run with root privilege)
        """
        self._log = logging.getLogger(type(self).__name__)
        self._who = who
        self._why = why
        if mode not in ('block', 'delay'):
            raise ValueError("Mode must be 'block' or 'delay'")
        self._mode = mode
        self._connection: Optional[jeep_io.DBusConnection] = None
        self._message_generator = login1_msggen.Manager()
        self._sleep_lock: Optional[jeep.FileDescriptor] = None


    def inhibit_sleep(self) -> bool:
        """
        Inhibit sleep until `allow_sleep` is called.
        :return: True if a new lock was taken (i.e. sleep was not already being inhibited), False if no new lock was taken.
        """
        if not self._connection:
            raise ValueError("No D-Bus connection is active. This resource must be opened in a 'with' block.")
        if self._sleep_lock:
            self._log.debug("Did not take a new lock, a lock is already held.")
            return False
        msg = self._connection.send_and_get_reply(
            self._message_generator.Inhibit(what=self._INHIBIT_WHAT, who=self._who, why=self._why, mode=self._mode))
        self._sleep_lock = msg.body[0]
        if (fd := self._sleep_lock.fileno()) < 0:
            raise ValueError(f'Invalid file descriptor: {fd}.')
        return True

    def allow_sleep(self) -> bool:
        """
        Allow the system to sleep.
        :return: True if a lock was released (i.e. sleep was already being inhibited), False if sleep was not being
        inhibited (requiring no action to be taken).
        """
        if self._sleep_lock is None:
            self._log.warning("Received a call to allow sleep when no sleep inhibition is in place.")
            return False
        try:
            self._sleep_lock.close()
        except Exception as e:
            self._log.warning("Unable to clsoe sleep lock", exc_info=e)
        self._sleep_lock = None
        return True

    def is_inhibiting(self) -> bool:
        return self._sleep_lock is not None

    def __enter__(self) -> 'SleepInhibitor':
        self._connection = jeep_io.open_dbus_connection(bus='SYSTEM', enable_fds=True)
        self._connection.__enter__()
        return self

    def __exit__(self, exc_type: any, exc_val: any, exc_tb: any):
        if self._connection:
            self._connection.close()
        if self._sleep_lock:
            self.allow_sleep()
        self._connection = None
