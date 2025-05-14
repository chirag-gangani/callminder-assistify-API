import logging
from pathlib import Path

def setup_logging():
    logging.basicConfig(
        level=logging.ERROR,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)
    Path("logs").mkdir(exist_ok=True)
    file_handler = logging.FileHandler('logs/app.log')
    file_handler.setLevel(logging.ERROR)
    logger.addHandler(file_handler)
    return logger