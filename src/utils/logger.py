import logging
from datetime import datetime
import os
from typing import Optional, Dict
from logging.handlers import RotatingFileHandler

# Global dictionary to track logger instances
_LOGGERS: Dict[str, logging.Logger] = {}

def setup_logger(name: str, log_dir: str = 'trading_logs') -> logging.Logger:
    """
    Enhanced logger setup with rotation and cleanup
    
    Args:
        name: Logger name (e.g., 'ForexBot', 'MT5Trader')
        log_dir: Directory for log files
        
    Returns:
        logging.Logger: Configured logger instance with auto-cleanup
    """
    # If logger already exists, return it
    if name in _LOGGERS:
        return _LOGGERS[name]

    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
        
    logger = logging.getLogger(name)
    
    # Clear any existing handlers
    logger.handlers.clear()
    
    try:
        # Console Handler - ERROR only
        console_handler = logging.StreamHandler()
        console_formatter = logging.Formatter('%(levelname)s - %(message)s')
        console_handler.setFormatter(console_formatter)
        console_handler.setLevel(logging.ERROR)
        
        # File Handler with Rotation - All levels
        log_file = os.path.join(log_dir, f'{name.lower()}.log')
        
        # Create a rotating handler that:
        # - Rotates when file reaches 512KB
        # - Keeps only 3 backup files
        # - Deletes the oldest file when rotating beyond 3 backups
        file_handler = RotatingFileHandler(
            filename=log_file,
            maxBytes=512*1024,    # 512KB
            backupCount=3,        # Keep only 3 backup files
            encoding='utf-8',
            delay=True            # Don't create file until first write
        )
        
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
        
        # Log rotation settings
        impl_logger = get_implementation_logger(log_dir)
        impl_logger.info(f"""
        Logger Setup for {name}:
        - Main log file: {log_file}
        - Max file size: 512KB
        - Backup count: 3
        - Rotation behavior: Will delete oldest file when rotating beyond 3 backups
        """)
        
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
    """Get or create implementation logger with rotation"""
    if 'Implementation' in _LOGGERS:
        return _LOGGERS['Implementation']
        
    logger = logging.getLogger('Implementation')
    logger.handlers.clear()
    
    impl_file = os.path.join(log_dir, 'implementation.log')
    
    handler = RotatingFileHandler(
        filename=impl_file,
        maxBytes=512*1024,    # 512KB
        backupCount=2,        # Keep only 2 backup files
        encoding='utf-8',
        delay=True
    )
    formatter = logging.Formatter('%(asctime)s - Implementation - %(message)s')
    handler.setFormatter(formatter)
    handler.setLevel(logging.INFO)
    
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    
    _LOGGERS['Implementation'] = logger
    return logger