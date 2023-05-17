import importlib
import logging
import pkgutil
from typing import Iterable

import src.condition.implementations as implementations
from src.condition.inhibiting_condition import InhibitingCondition


class InhibitingConditionRegistrar:

    _REGISTER_FUNCTION_NAME = "register"
    def __init__(self):
        self._inhibiting_conditions = list()
        self._log = logging.getLogger(type(self).__name__)

    def __contains__(self, item: InhibitingCondition) -> bool:
        return item in self._inhibiting_conditions

    def __len__(self) -> int:
        return len(self._inhibiting_conditions)

    def __iter__(self) -> Iterable[InhibitingCondition]:
        return self._inhibiting_conditions.__iter__()

    def accept(self, inhibiting_process: InhibitingCondition) -> None:
        if inhibiting_process in self:
            raise ValueError(f"Inhibiting Condition: {inhibiting_process} has already been registered.")
        self._log.info(f"Registering {inhibiting_process.name}")
        self._inhibiting_conditions.append(inhibiting_process)

    def scan(self) -> None:
        importlib.invalidate_caches()
        for _finder, name, _ispkg in pkgutil.iter_modules(path=implementations.__path__, prefix=implementations.__name__+"."):
            module = importlib.import_module(name)
            if self._REGISTER_FUNCTION_NAME in dir(module):
                self._log.info(f"Discovered Inhibiting Condition(s): {name}.  Attempting to register.")
                num_conditions = len(self)
                try:
                    module.register(self)
                except Exception as e:
                    self._log.warning(f"Failed to register Inhibiting Condition(s): {name}.")
                    continue
                self._log.info(f"Added {len(self) - num_conditions} inhibiting condition(s) from: {name}.")

    def clear(self) -> None:
        while self._inhibiting_conditions:
            self._inhibiting_conditions.pop()


registrar = InhibitingConditionRegistrar()