import logging
import subprocess
import re
from datetime import timedelta

from common import config_provider
from client.inhibiting_condition import InhibitingCondition

config_root_key = "sshd"
period_key = "period_min"
# max inhibiting periods (i.e. inactive user)
#
max_periods_key = "max_periods"

class SshdInhibitor(InhibitingCondition):

    """
    Inhibits sleep while an ssh client is connected to sshd.  Only inhibits for incoming session, outgoing sessions with
    a remote host from this box do not cause sleep inhibition
    """

    def __init__(self, period: timedelta, max_periods: int):
        name = f"{type(self).__name__}"
        super().__init__(name=name, period=period)
        self._log = logging.getLogger(name)

        if max_periods < 0:
            self._log.warning("max_periods is negative, must be >= 0, setting to 0.")
            max_periods = 0

        self._max_periods = max_periods
        self._matcher = re.compile(r"\sssh\s")
        self._periods_inhibited = 0

    def does_inhibit(self) -> bool:
        out = subprocess.run(["last", "-p", "now"], capture_output=True, text=True)
        if out.returncode != 0:
            self._log.warning("Error return code from 'last' command.  Could not check condition")

        if self._matcher.search(out.stdout) is not None:
            self._periods_inhibited += 1
        else:
            self._periods_inhibited = 0

        return 0 < self._periods_inhibited <= self._max_periods

def register(registrar: 'InhibtingConditionRegistrar') -> None:
    if not config_provider.key_exists([config_root_key]):
        logging.debug("Skipping registration of sshd inhibitor. Configuration is absent.")
        return

    period_min_str = config_provider.get_value(key_path=[config_root_key, period_key], default="5")
    max_periods_str = config_provider.get_value(key_path=[config_root_key, max_periods_key],
                                                default="2147483647")
    try:
        period_min = float(period_min_str)
    except Exception:
        raise ValueError(f"Could not parse period_min.")
    try:
        max_periods = int(max_periods_str)
    except Exception:
        raise ValueError(f"Could not parse max_periods")

    period = timedelta(minutes=period_min)
    logging.info(f"Registering sshd with a period: {period}, max_periods {max_periods}")
    registrar.accept(SshdInhibitor(period=period, max_periods=max_periods))
