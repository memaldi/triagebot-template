"""TriageBot application package."""
import logging.config
from pathlib import Path

_config_file = Path(__file__).parent.parent / "logging.ini"
if _config_file.exists():
    logging.config.fileConfig(_config_file, disable_existing_loggers=False)

