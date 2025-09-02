import logging

from .money import Cents, fmt_money, from_cents


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.level:
        logger.setLevel(logging.DEBUG)
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter('[%(levelname)s] %(name)s: %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger


def format_money_for_logging(cents: Cents) -> str:
    """
    Format cents for logging display.
    
    Args:
        cents: Integer cents
        
    Returns:
        Formatted string like "$1.25"
    """
    return fmt_money(cents)


def cents_to_float_for_db(cents: Cents) -> float:
    """
    Convert cents to float for database storage.
    
    Args:
        cents: Integer cents
        
    Returns:
        Float dollar amount for existing DB schema
    """
    return from_cents(cents)