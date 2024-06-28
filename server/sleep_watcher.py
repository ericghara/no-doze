import logging
import signal
from typing import *

import jeepney as _jeep
import jeepney.io.blocking as _jeep_io

from server.sleep_inhibitor import SleepInhibitor


class SleepWatcher:

    # Inhibitor
    _WHO = 'no-doze sleep watcher'
    _WHY = 'last gasp check'
    _MODE = 'delay'

    # Dbus
    _INTERFACE = 'org.freedesktop.login1.Manager'
    _PATH = '/org/freedesktop/login1'
    _MEMBER = 'PrepareForSleep'
    _TYPE = 'signal'

    def __init__(self, before_sleep_callback: Optional[Callable] = None, awake_callback: Optional[Callable] = None):
        """
        For the prepare_callback sleep will be delayed as long as the callback is executing (should be << 5 seconds). If
        the callback just sends a signal for another thread or process to do work, consider adding a delay or waiting
        for a completion response before returning from the callback to ensure necessary work is completed.
        :param before_sleep_callback: called before entering sleep
        :param awake_callback: called on awaking from sleep
        """
        self._log = logging.getLogger(type(self).__name__)
        self._sleep_delay: Optional[SleepInhibitor] = None
        self._match_rule = _jeep.MatchRule(
            type=self._TYPE,
            interface=self._INTERFACE,
            member=self._MEMBER,
            path=self._PATH
        )
        self._connection: Optional[_jeep_io.DBusConnection] = None
        self._sleep_fn = before_sleep_callback
        self._awake_fn = awake_callback
        self._run = False

    def run(self):
        """
        Begin watching for PrepareForSleep signals.  Execute callbacks upon receiving signal.  This call blocks
        indefinitely so should probably be run on another thread.
        :return:
        """
        if self._connection is None:
            raise RuntimeError("Must __enter__ before calling.")
        if self._sleep_fn is None and self._awake_fn is None:
            self._log.warning("SleepWatcher running without any callbacks. Essentially does nothing.")

        self._run = True
        with self._connection.filter(self._match_rule) as signals:
            self._sleep_delay.inhibit_sleep()
            while self._run:
                try:
                    signal = self._connection.recv_until_filtered(signals)
                except Exception as e:
                    self._log.debug("Caught an error while receiving.  Going down?", exc_info=e)
                    continue
                if signal.body[0]:
                    self._log.debug('Caught PrepareForSleep signal.')
                    if self._sleep_fn:
                        self._log.debug('Executing prepare callback.')
                        self._sleep_fn()
                    self._log.debug('Releasing sleep delay lock.')
                    self._sleep_delay.allow_sleep()
                else:
                    self._log.debug('Caught awake signal. Taking sleep delay lock.')
                    self._sleep_delay.inhibit_sleep()
                    if self._awake_fn:
                        self._log.debug('Executing awake callback.')
                        self._awake_fn()

    def __enter__(self) -> 'SleepWatcher':
        if self._connection is not None:
            raise RuntimeError("Attempting to enter an open SleepWatcher.")

        self._sleep_delay = SleepInhibitor(who=self._WHO, why=self._WHY, mode=self._MODE).__enter__()
        self._connection = _jeep_io.open_dbus_connection(bus='SYSTEM')
        _jeep_io.Proxy(_jeep.message_bus, self._connection).AddMatch(self._match_rule)
        return self

    def __exit__(self, exec_type: any, exec_value: any, exec_tb: any):
        self._run = False
        if self._connection is not None:
            self._connection.close()
            self._connection = None
        if self._sleep_delay:
            self._sleep_delay.__exit__(None, None, None)
            self._sleep_delay = None


if __name__ == '__main__':
    """
    Toy Implementation b/c this is hard to unit-test
    """
    logging.basicConfig(level=logging.DEBUG)
    sleep_callback = lambda: print('Prepare Callback: bye, bye.')
    awake_cakkback = lambda: print('Awake Callback: hello.')
    sw = SleepWatcher(awake_callback=awake_cakkback, before_sleep_callback=sleep_callback)
    signal.signal(signalnum=signal.SIGINT, handler=lambda sig, frame: sw.__exit__(None, None, None))
    with sw as sw:
        sw.run()





