"""
Logger - Logging utility for the application.
Provides centralized logging configuration and utilities.
"""

import logging
import os
from datetime import datetime
from typing import Optional


class Logger:
    """Custom logger with file and console handlers."""
    
    _loggers = {}
    
    @classmethod
    def get_logger(cls, name: str, log_level: Optional[str] = None) -> logging.Logger:
        """
        Get or create a logger with the specified name.
        
        Args:
            name: Logger name (usually __name__ of the calling module)
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            
        Returns:
            Configured logger instance
        """
        if name in cls._loggers:
            return cls._loggers[name]
        
        logger = logging.getLogger(name)
        
        # Set log level
        level = getattr(logging, (log_level or os.getenv('LOG_LEVEL', 'INFO')).upper())
        logger.setLevel(level)
        
        # Avoid adding handlers multiple times
        if not logger.handlers:
            # Create logs directory if it doesn't exist
            log_dir = os.path.join(os.getcwd(), 'logs')
            os.makedirs(log_dir, exist_ok=True)
            
            # File handler with timestamp
            log_file = os.path.join(log_dir, f'document_extraction_{datetime.now().strftime("%Y%m%d")}.log')
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setLevel(level)
            
            # Console handler
            console_handler = logging.StreamHandler()
            console_handler.setLevel(level)
            
            # Formatter
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            file_handler.setFormatter(formatter)
            console_handler.setFormatter(formatter)
            
            # Add handlers
            logger.addHandler(file_handler)
            logger.addHandler(console_handler)
        
        cls._loggers[name] = logger
        return logger


def get_logger(name: str, log_level: Optional[str] = None) -> logging.Logger:
    """
    Convenience function to get a logger.
    
    Args:
        name: Logger name
        log_level: Optional log level override
        
    Returns:
        Logger instance
    """
    return Logger.get_logger(name, log_level)


def set_global_log_level(level: str):
    """
    Set the global logging level for all loggers.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    log_level = getattr(logging, level.upper())
    
    for logger in Logger._loggers.values():
        logger.setLevel(log_level)
        for handler in logger.handlers:
            handler.setLevel(log_level)


def log_function_call(logger: logging.Logger, func_name: str, **kwargs):
    """
    Log a function call with parameters.
    
    Args:
        logger: Logger instance
        func_name: Name of the function being called
        **kwargs: Function parameters
    """
    params = ', '.join([f"{k}={v}" for k, v in kwargs.items()])
    logger.debug(f"Calling {func_name}({params})")


def log_error(logger: logging.Logger, error: Exception, context: Optional[str] = None):
    """
    Log an error with context.
    
    Args:
        logger: Logger instance
        error: Exception object
        context: Optional context information
    """
    error_msg = f"{type(error).__name__}: {str(error)}"
    if context:
        error_msg = f"{context} - {error_msg}"
    logger.error(error_msg, exc_info=True)


def log_performance(logger: logging.Logger, operation: str, duration: float):
    """
    Log performance metrics.
    
    Args:
        logger: Logger instance
        operation: Name of the operation
        duration: Duration in seconds
    """
    logger.info(f"Performance: {operation} took {duration:.4f} seconds")


class PerformanceTimer:
    """Context manager for timing operations."""
    
    def __init__(self, logger: logging.Logger, operation: str):
        """
        Initialize performance timer.
        
        Args:
            logger: Logger instance
            operation: Name of the operation being timed
        """
        self.logger = logger
        self.operation = operation
        self.start_time = None
    
    def __enter__(self):
        """Start the timer."""
        import time
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Stop the timer and log the duration."""
        import time
        duration = time.time() - self.start_time
        log_performance(self.logger, self.operation, duration)
        return False
