import logging
from datetime import datetime
import os
from typing import Optional, Dict

# Global dictionary to track logger instances
_LOGGERS: Dict[str, logging.Logger] = {}

def setup_logger(name: str, log_dir: str = 'trading_logs') -> logging.Logger:
    """
    Enhanced logger setup with strictly separated console and file handlers
    
    Args:
        name: Logger name (e.g., 'ForexBot', 'MT5Trader')
        log_dir: Directory for log files
        
    Returns:
        logging.Logger: Configured logger instance
    """
    # If logger already exists, return it
    if name in _LOGGERS:
        return _LOGGERS[name]

    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
        
    logger = logging.getLogger(name)
    
    # Clear any existing handlers
    logger.handlers.clear()
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    try:
        # Console Handler - ERROR only
        console_handler = logging.StreamHandler()
        console_formatter = logging.Formatter('%(levelname)s - %(message)s')
        console_handler.setFormatter(console_formatter)
        console_handler.setLevel(logging.ERROR)
        
        # File Handler - All levels
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
        
        # Store logger in global dictionary
        _LOGGERS[name] = logger
        
        # Log setup only for non-implementation loggers
        if name != 'Implementation':
            impl_logger = get_implementation_logger(log_dir)
            impl_logger.info(f"Logger configuration updated for {name}")
            impl_logger.info(f"Full debug logging enabled in {log_file}")
            
        return logger
        
    except Exception as e:
        # Fallback logging configuration
        logging.basicConfig(
            level=logging.ERROR,
            format='%(levelname)s - %(message)s'
        )
        basic_logger = logging.getLogger(name)
        basic_logger.error(f"Error setting up logger: {str(e)}")
        return basic_logger

def get_implementation_logger(log_dir: str = 'trading_logs') -> logging.Logger:
    """Get or create implementation logger"""
    if 'Implementation' in _LOGGERS:
        return _LOGGERS['Implementation']
        
    logger = logging.getLogger('Implementation')
    logger.handlers.clear()
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    impl_file = os.path.join(log_dir, f'implementation_changes_{timestamp}.log')
    
    handler = logging.FileHandler(impl_file, encoding='utf-8')
    formatter = logging.Formatter('%(asctime)s - Implementation - %(message)s')
    handler.setFormatter(formatter)
    handler.setLevel(logging.INFO)
    
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    
    _LOGGERS['Implementation'] = logger
    return logger