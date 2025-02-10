import logging
from pathlib import Path

def setup_logging():
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)
    
    # Create logs directory if it doesn't exist
    Path("logs").mkdir(exist_ok=True)
    
    # Add file handler
    file_handler = logging.FileHandler('logs/app.log')
    file_handler.setLevel(logging.DEBUG)
    logger.addHandler(file_handler)
    
    return logger