import logging
import os
from typing import Optional

import dbus
from _dbus_bindings import UnixFd
from dbus.proxies import ProxyObject, Interface


class FileDescriptorLock:

    """
    An abstraction around a FileDescriptor lock.  Extreme care should be made to ensure that FileDescriptorLocks
    are eventually closed even in during failure modes of a program.  Explicit `take` and `release` methods are provided
    as well as support for `with` statements which allow holding the lock for the duration of the with block.
    """

    def __init__(self, descriptor_obj: UnixFd):
        self._log = logging.getLogger(type(self).__name__)
        self._descriptor_obj = descriptor_obj
        self._open_descriptor = None

    def take(self):
        self.__enter__()

    def release(self):
        if self._open_descriptor is not None:
            try:
                os.close(self._open_descriptor)
                self._open_descriptor = None
            except Exception as e:
                self._log.warning(f"Unable to close the file descriptor: {self._open_descriptor}.", e)


    def __enter__(self) -> 'FileDescriptorLock':
        if self._open_descriptor is not None:
            self._log.warning("The descriptor has already been taken.  Do not reuse this object.")
            raise ValueError("This descriptor has already been taken.")
        try:
            self._open_descriptor = self._descriptor_obj.take()
            return self
        except Exception as e:
            raise ValueError("Unable to take the file descriptor.", e)
    def __exit__(self, exc_type: any, exc_val: any, exc_tb: any):
        self.release()

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
        self._system_bus: Optional[dbus.SystemBus] = None
        self._login_proxy: Optional[ProxyObject] = None
        self._login_manager_interface: Optional[Interface] = None
        self._sleep_lock: Optional[FileDescriptorLock] = None


    def inhibit_sleep(self) -> bool:
        """
        Inhibit sleep until `allow_sleep` is called.
        :return: True if a new lock was taken (i.e. sleep was not already being inhibited), False if no new lock was taken.
        """
        if not self._login_manager_interface:
            raise ValueError("No D-Bus connection is active. This resource must be opened in a 'with' block.")
        if self._sleep_lock:
            self._log.debug("Did not take a new lock, a lock is already held.")
            return False
        descriptor_obj = self._login_manager_interface.Inhibit(self._INHIBIT_WHAT, self._who, self._why, self._mode)
        self._sleep_lock = FileDescriptorLock(descriptor_obj)
        self._sleep_lock.take()
        return True

    def allow_sleep(self) -> bool:
        """
        Allow the system to sleep.
        :return: True if a lock was released (i.e. sleep was already being inhibited), False if sleep was not being
        inhibited (requiring no action to be taken).
        """
        if not self._sleep_lock:
            self._log.warning("Received a call to allow sleep when no sleep inhibition is in place.")
            return False
        self._sleep_lock.release()
        self._sleep_lock = None
        return True

    def is_inhibiting(self) -> bool:
        return self._sleep_lock is not None

    def __enter__(self) -> 'SleepInhibitor':
        self._system_bus = dbus.SystemBus()
        self._login_proxy = self._system_bus.get_object(self._LOGIND_BUS_NAME, self._LOGIND_OBJECT_PATH)
        self._login_manager_interface = dbus.Interface(self._login_proxy, dbus_interface=self._LOGIND_MANAGER_INTERFACE)
        return self

    def __exit__(self, exc_type: any, exc_val: any, exc_tb: any):
        if self._system_bus:
            self._system_bus.close()
        if self._sleep_lock:
            self.allow_sleep()
        self._system_bus = None
        self._login_proxy = None
        self._login_manager_interface = None
