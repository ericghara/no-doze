from pathlib import Path

import yaml

config_path = Path(__file__).parent / "resources/config.yml"

def _load_config() -> dict:
    with config_path.open() as f:
        return yaml.load(f, Loader=yaml.CLoader)

config_yml: dict = _load_config()