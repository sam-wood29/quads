import logging
import os

def setup_logger(name=None,
    log_file='logs/quads.log',
    level=logging.INFO,
    mode='w',
    console_handler = True,
    formatter_input: str = '%(message)s\n'
    # Some examples of nice formatters to use
    # '%(asctime)s - %(name)s - %(levelname)s\n%(message)s\n'
) -> logging.Logger:
    """"""
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # ???
    if logger.handlers:
        return logger # avoid duplicate handlers
    
    # Ensure the logs directory exists:
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    formatter = logging.Formatter(
        formatter_input
    )

    # Console hander if:
    if console_handler:
        ch = logging.StreamHandler()
        ch.setFormatter(formatter)
        logger.addHandler(ch)
    
    # File handler
    fh = logging.FileHandler(log_file, mode=mode)
    fh.setFormatter(formatter)
    logger.addHandler(fh)

    return logger
