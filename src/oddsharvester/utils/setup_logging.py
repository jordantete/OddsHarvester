import logging
from logging.handlers import RotatingFileHandler
import os

DEFAULT_LOG_DIR = "logs"
DEFAULT_LOG_FILE_NAME = "app.log"


def setup_logger(
    log_level: int = logging.INFO,
    save_to_file: bool = False,
    log_file: str = DEFAULT_LOG_FILE_NAME,
    log_dir: str = DEFAULT_LOG_DIR,
    max_file_size: int = 5 * 1024 * 1024,  # 5 MB
    backup_count: int = 5,
):
    """
    Sets up logging for both console and optionally file output.

    Args:
        log_level (int): The logging level (e.g., logging.INFO, logging.DEBUG).
        save_to_file (bool): Whether to save logs to a file.
        log_file (str): The name of the log file.
        log_dir (str): Directory where log files will be stored.
        max_file_size (int): Maximum size of a single log file in bytes.
        backup_count (int): Number of backup log files to retain.
    """
    log_formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(log_formatter)
    handlers = [console_handler]

    if save_to_file:
        os.makedirs(log_dir, exist_ok=True)
        log_file_path = os.path.join(log_dir, log_file)
        file_handler = RotatingFileHandler(log_file_path, maxBytes=max_file_size, backupCount=backup_count)
        file_handler.setFormatter(log_formatter)
        handlers.append(file_handler)

        logging.basicConfig(level=log_level, handlers=handlers)
        logging.info(f"Logging initialized. Log level: {logging.getLevelName(log_level)}")

        if save_to_file:
            logging.info(f"Logs will be saved to {log_file_path}")
    else:
        logging.basicConfig(level=log_level, handlers=handlers)
        logging.info(f"Logging initialized. Log level: {logging.getLevelName(log_level)} (No file output)")
