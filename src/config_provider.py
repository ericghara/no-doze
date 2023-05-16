import logging
from datetime import timedelta
from pathlib import Path
from typing import Optional

import yaml

_config_path = Path(__file__).parent / "resources/config.yml"
_config_yml: dict = {}

_log = logging.getLogger("config_provider")

def _load_file() -> None:
    global _config_yml
    with _config_path.open() as f:
        _config_yml = yaml.load(f, Loader=yaml.CLoader)


def _load_string(yml_str: str) -> None:
    global _config_yml
    _config_yml = yaml.load(yml_str, Loader=yaml.CLoader)


_load_file()


def get_value(key_path: list[str], default_val: Optional[str] = None) -> str:
    """
    Retrieves values from the nested `config_yml` `dict`.  The optional default value is returned
    if the key is not found.  If the query or yaml schema cause traversal though a scalar value,
    an error is thrown as this indicates not a missing key, but a misconfiguration.
    :param key_path: a series of key elements delimited by a `.`, *i.e.* `path.to.key`
    :param default_val:
    :return: found key or default, as a string
    :raise: ValueError if provided path would cause traversal through a scalar value or
    if the path does not exist in the dictionary and not default was provided.
    """
    val = _config_yml
    for i in range(0, len(key_path) - 1):
        if val is None:
            break
        if type(val) is not dict:
            raise ValueError("Yaml schema contained scalar/list value where a dict was expected. ")
        val = val.get(key_path[i])
    if val is None:
        if default_val is not None:
            _log.info(f"Unable to find value for key: {'.'.join(key_path)}, using default value {default_val}")
            return str(default_val)
        raise ValueError("Unable to provide a value.  Key not found.")
    found_val = val.get(key_path[-1])
    if type(found_val) in {int, float, str, bool}:
        return str(found_val)
    raise ValueError("Yaml schema contained dict or list where a scalar was expected. ")


def get_period_min(key_path: list[str], default: timedelta) -> timedelta:
    raw_min = float(get_value(key_path, None))
    if raw_min is None:
        return default
    return timedelta(minutes=raw_min)
