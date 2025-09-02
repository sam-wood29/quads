"""
All game logic uses integer cents. Never store floats in state.

This module provides safe money primitives for converting between
dollar amounts and integer cents, with validation and formatting.
"""


# Type alias for cents - all internal arithmetic uses this
Cents = int


def to_cents(amount: float | str | int) -> Cents:
    """
    Convert dollar amount to cents.
    
    Args:
        amount: Dollar amount as float, string, or int
        
    Returns:
        Integer cents
        
    Raises:
        ValueError: If more than 2 decimal places or invalid format
    """
    if isinstance(amount, str):
        # Handle string input like "12.34" or "12"
        try:
            # Check for more than 2 decimal places
            if '.' in amount:
                parts = amount.split('.')
                if len(parts) != 2:
                    raise ValueError(f"Invalid decimal format: {amount}")
                if len(parts[1]) > 2:
                    raise ValueError(f"Too many decimal places: {amount}")
            
            # Convert to float first to handle edge cases
            float_val = float(amount)
        except ValueError as e:
            raise ValueError(f"Invalid amount format: {amount}") from e
    elif isinstance(amount, (int, float)):
        float_val = float(amount)
    else:
        raise ValueError(f"Unsupported type: {type(amount)}")
    
    # Convert to cents and validate
    cents = round(float_val * 100)
    
    # Check for overflow (though unlikely with reasonable poker amounts)
    if cents > 2**31 - 1:  # Max 32-bit signed int
        raise ValueError(f"Amount too large: {amount}")
    
    return cents


def from_cents(cents: Cents) -> float:
    """
    Convert cents back to dollars (for display only).
    
    Args:
        cents: Integer cents
        
    Returns:
        Float dollar amount
    """
    if not isinstance(cents, int):
        raise ValueError(f"Cents must be integer, got {type(cents)}")
    
    return cents / 100.0


def fmt_money(cents: Cents) -> str:
    """
    Format cents as currency string.
    
    Args:
        cents: Integer cents
        
    Returns:
        Formatted string like "$12.34"
    """
    if not isinstance(cents, int):
        raise ValueError(f"Cents must be integer, got {type(cents)}")
    
    dollars = from_cents(cents)
    return f"${dollars:.2f}"


def add_cents(*values: Cents) -> Cents:
    """
    Safe addition of cent amounts with overflow protection.
    
    Args:
        *values: Integer cents to add
        
    Returns:
        Sum in cents
        
    Raises:
        ValueError: If overflow would occur
    """
    if not values:
        return 0
    
    # Validate all inputs are integers
    for val in values:
        if not isinstance(val, int):
            raise ValueError(f"All values must be integers, got {type(val)}")
    
    # Check for overflow before adding
    total = sum(values)
    if total > 2**31 - 1:
        raise ValueError("Sum would overflow 32-bit integer")
    
    return total


def nonneg(cents: Cents) -> Cents:
    """
    Assert that cents amount is non-negative.
    
    Args:
        cents: Integer cents
        
    Returns:
        Same cents value if non-negative
        
    Raises:
        ValueError: If cents is negative
    """
    if not isinstance(cents, int):
        raise ValueError(f"Cents must be integer, got {type(cents)}")
    
    if cents < 0:
        raise ValueError(f"Negative amount not allowed: {cents}")
    
    return cents
