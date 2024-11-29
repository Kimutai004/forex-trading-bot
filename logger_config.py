import logging
from datetime import datetime
import os
from typing import Optional

def setup_logger(name: str, log_dir: str = 'trading_logs') -> logging.Logger:
    """
    Standardized logger setup for all components
    
    Args:
        name: Logger name (e.g., 'ForexBot', 'MT5Trader')
        log_dir: Directory for log files
        
    Returns:
        logging.Logger: Configured logger instance
    """
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
        
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
        
    # Create timestamp for this session
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    try:
        # Console Handler
        console_handler = logging.StreamHandler()
        console_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(console_formatter)
        console_handler.setLevel(logging.INFO)
        
        # File Handler
        log_file = os.path.join(log_dir, f'{name.lower()}_{timestamp}.log')
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - [%(levelname)s] - %(message)s\n'
            'File: %(filename)s:%(lineno)d\n'
            'Function: %(funcName)s\n'
            '----------------------------------------'
        )
        file_handler.setFormatter(file_formatter)
        file_handler.setLevel(logging.DEBUG)
        
        # Add handlers to logger
        logger.addHandler(console_handler)
        logger.addHandler(file_handler)
        logger.setLevel(logging.DEBUG)
        
        # Log initial setup
        logger.info(f"Logger initialized for {name}")
        logger.info(f"Detailed logs will be saved to: {log_file}")
        
        return logger
        
    except Exception as e:
        # Fallback basic logger if something goes wrong
        logging.basicConfig(level=logging.INFO)
        basic_logger = logging.getLogger(name)
        basic_logger.error(f"Error setting up logger: {str(e)}")
        return basic_logger