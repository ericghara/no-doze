import importlib
import logging
import pkgutil
from typing import Iterable

import src.trigger.implementations as implementations
from src.trigger.inhibiting_process import InhibitingProcess


class InhibitingProcessRegistrar:

    _REGISTER_FUNCTION_NAME = "register"
    def __init__(self):
        self._inhibiting_processes = list()
        self._log = logging.getLogger(type(self).__name__)

    def __contains__(self, item: InhibitingProcess) -> bool:
        return item in self._inhibiting_processes

    def __len__(self) -> int:
        return len(self._inhibiting_processes)

    def __iter__(self) -> Iterable[InhibitingProcess]:
        return self._inhibiting_processes.__iter__()

    def accept(self, inhibiting_process: InhibitingProcess) -> None:
        if inhibiting_process in self:
            raise ValueError(f"Inhibiting Process: {inhibiting_process} has already been registered.")
        self._log.info(f"Registering {inhibiting_process.name}")
        self._inhibiting_processes.append(inhibiting_process)

    def scan(self) -> None:
        importlib.invalidate_caches()
        for _finder, name, _ispkg in pkgutil.iter_modules(path=implementations.__path__, prefix=implementations.__name__+"."):
            module = importlib.import_module(name)
            if self._REGISTER_FUNCTION_NAME in dir(module):
                self._log.info(f"Discovered Inhibiting Process: {name}.  Attempting to register.")
                try:
                    module.register(self)
                except Exception as e:
                    self._log.warning(f"Failed to register Inhibiting Process: {name}.")
                    continue
                self._log.info(f"Successfully registered Inhibiting Process: {name}.")

    def clear(self) -> None:
        while self._inhibiting_processes:
            self._inhibiting_processes.pop()


registrar = InhibitingProcessRegistrar()