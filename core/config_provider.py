import logging
from datetime import timedelta
from pathlib import Path
from typing import Optional, Dict, List

import yaml

_config_path = Path(__file__).parent / "../resources/config.yml"
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
    Retrieves values from the `config_yml`.  The optional default value is returned
    if the key is not found.  If the query or yaml schema cause traversal though a scalar value,
    an error is thrown as this indicates not a missing key, but a misconfiguration.
    :param key_path: a series of key elements delimited by a `.`, *i.e.* `path.to.key`
    :param default_val:
    :return: found key or default, as a string
    :raise: ValueError if provided path would cause traversal through a scalar value or
    if the path does not exist in the dictionary and not default was provided.
    """
    if type(key_path) is not list:
        raise ValueError("key_path should be a list of path elements.")
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
    found_val = val.get(key_path[-1], default_val)
    if type(found_val) in {int, float, str, bool}:
        return str(found_val)
    raise ValueError("Yaml schema contained dict or list where a scalar was expected. ")

def get_object(key_path: list[str], default: Optional[List|Dict]=None) -> List|Dict:
    """
    Gets a non-scalar value (list or dict) from the config.  A default may be provided, otherwise an error will be raised
    if the key is not found.  If the found value is a scalar **or** while traversing to the value, traversal *through* a scaler
    occurs an error is thrown (irrespective of if a default value was provided).  While slightly opinionated, traversing through
    a scalar means that something is wrong with the YAML schema, so it's better to fail fast.
    :param key_path: List[str] of path elements i.e. ["path","to","key"]
    :param default: value to be returned if key is not found
    :return:
    """
    if type(key_path) is not list:
        raise ValueError("key_path should be a list of path elements.")
    path = [*key_path] # defensive copy
    path.append(None) # sentinel
    cur_val = _config_yml
    for element in path:
        if cur_val is None:
            cur_val = default
            break
        if type(cur_val) not in (list, dict):
            _log.warning("Encountered a scalar value while traversing to key.  Check your config.yml.")
            raise ValueError("YAML schema is incorrect.")
        if element is not None:
            cur_val = cur_val.get(element)
    if cur_val is None:
        raise ValueError(f"Unable to find a value for path {key_path}")
    return cur_val

def key_exists(key_path: list[str]) -> bool:
    """
    Query if a key exists.
    :param key_path: List[str] of path elements i.e. ["path","to","key"]
    :return:
    """
    if type(key_path) is not list:
        raise ValueError("key_path should be a list of path elements.")

    path = [*key_path] # defensive copy
    path.append(None) # sentinel
    cur_val = _config_yml
    for element in path:
        if cur_val is None:
            return False
        if element is not None:
            cur_val = cur_val.get(element)
    return True


def get_period_min(key_path: list[str], default: timedelta) -> timedelta:
    """
    Parses a number (float or int) from the config file and returns it as a timedelta of minutes. Uses `get_value` under
    the hood, so refer to documentation of that function for usage details.
    :param key_path: List[str] of path elements i.e. ["path","to","key"]
    :param default: a default timedelta to be returned in the case no key is found
    :return:
    """
    raw_min = float(get_value(key_path, None))
    if raw_min is None:
        return default
    return timedelta(minutes=raw_min)
