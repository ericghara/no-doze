from pathlib import Path

import yaml

config_path = Path(__file__).parent / "resources/config.yaml"
config_yml: dict = None

with config_path.open() as f:
    config_yml = yaml.load(f, Loader=yaml.CLoader)