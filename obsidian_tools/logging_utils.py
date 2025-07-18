import sys
from pathlib import Path
from loguru import logger
import logging


class PropagateHandler(logging.Handler):
    def emit(self, record):
        logging.getLogger(record.name).handle(record)


def setup_logging(name: str) -> Path:
    """Set up logging to file and console."""
    log_dir = Path("logs") / name
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "out.log"
    logger.remove()
    logger.add(sys.stderr, level="INFO")
    logger.add(log_file, level="DEBUG")
    logger.add(PropagateHandler(), format="{message}")
    logger.info(f"Logging to {log_file}")
    return log_dir
