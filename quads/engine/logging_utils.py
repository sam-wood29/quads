import logging
import os

def setup_logger(name=None,
    log_file='logs/quads.log',
    level: int = logging.DEBUG,
    mode='a',
    console_handler = True,
    formatter_input: str = '%(message)s'
) -> logging.Logger:
    """"""
    logger = logging.getLogger(name)
    logger.setLevel(level)

    if logger.hasHandlers():
        logger.handlers.clear() # avoid duplicate handlers
    
    # Ensure the logs directory exists:
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    formatter = logging.Formatter(
        formatter_input
    )

    # Console hander if:
    if console_handler:
        ch = logging.StreamHandler()
        ch.setFormatter(formatter)
        ch.setLevel(level)
        logger.addHandler(ch)
    
    # File handler
    fh = logging.FileHandler(log_file, mode=mode)
    fh.setFormatter(formatter)
    fh.setLevel(level)
    logger.addHandler(fh)

    return logger
