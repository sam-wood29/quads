from quads.engine.validated_action import ValidatedAction
from quads.engine.enums import ActionType


def make_va_factory(hand):
    """
    Create a validation factory function bound to a specific hand.
    
    Args:
        hand: Hand instance with validate_action method
        
    Returns:
        Function that takes (player, action_type, amount_cents) and returns ValidatedAction
    """
    def validate_action(player, action_type, amount_cents):
        """Validate action using hand's existing validation logic."""
        return hand.validate_action(player, action_type, amount_cents)
    
    return validate_action