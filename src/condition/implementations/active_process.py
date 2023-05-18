import logging
import subprocess
from datetime import timedelta

from src import config_provider
from src.condition.inhibiting_condition import InhibitingCondition

config_root_key = "active-process"
processes_key = "processes"
name_key = "name"
period_min_key = "period_min"

class ActiveProcessInhibitor(InhibitingCondition):

    def __init__(self, process_name: str, period: timedelta):
        name = f"{type(self).__name__} - {process_name}"
        super().__init__(name=name, period=period)
        self._log = logging.getLogger(name)
        self._process_name = process_name


    def does_inhibit(self) -> bool:
        result = subprocess.run(["ps", "h", "-C", self._process_name], capture_output=True, text=True)
        return result.returncode == 0

def register(registrar: 'InhibitingProcessRegistrar') -> None:
    process_info = config_provider.get_object(key_path=[config_root_key, processes_key], default=list())
    for info in process_info:
        process_name = info.get(name_key)
        if type(process_name) is not str:
            raise ValueError("Unexpected type encountered for process name.")
        try:
            period_min = float(info.get(period_min_key))
        except Exception as e:
            raise ValueError(f"Could not parse the period_min for {process_name}.")
        period = timedelta(minutes=period_min)
        logging.info(f"Registering: {process_name} with a period of {period}")
        registrar.accept(ActiveProcessInhibitor(process_name=process_name, period=period))
