import logging

from src import config_provider

logging.basicConfig(level=config_provider.get_value(["logging_level"], "INFO"))