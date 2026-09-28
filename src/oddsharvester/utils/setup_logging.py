import logging


def setup_logger(log_level: int = logging.INFO) -> None:
    """Send logs to the console at the given level."""
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
    logging.basicConfig(level=log_level, handlers=[console_handler])
    logging.info(f"Logging initialized. Log level: {logging.getLevelName(log_level)} (No file output)")
