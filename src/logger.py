import logging, sys

def setup_logger():
    """Initialize root logger configuration"""
    root_logger = logging.getLogger('OddsPortalScraper')
    if not root_logger.handlers:
        root_logger.setLevel(logging.INFO)
        detailed_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s')
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(detailed_formatter)
        root_logger.addHandler(console_handler)