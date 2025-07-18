import sys
from pathlib import Path
from loguru import logger
import datetime


def setup_logging(log_dir_name: str) -> Path:
    """Sets up loguru logging."""
    log_dir = (
        Path("logs")
        / f"{log_dir_name}-{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}"
    )
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "out.log"

    logger.remove()
    logger.add(sys.stderr, level="INFO")
    logger.add(log_file, level="DEBUG")

    logger.info(f"Logging to {log_file}")
    return log_dir
