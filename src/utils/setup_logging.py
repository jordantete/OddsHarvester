import logging

def setup_logger(log_level: int = logging.INFO):
    """
    Sets up logging with options for console.

    Args:
        log_level (int): The logging level (e.g., logging.INFO, logging.DEBUG).
    """
    handlers = []

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    handlers.append(console_handler)

    logging.basicConfig(level=log_level, handlers=handlers)
    logging.info(f"Logging initialized. Log level: {logging.getLevelName(log_level)}")