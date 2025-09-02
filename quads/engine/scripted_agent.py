from typing import Iterator, Callable
from quads.engine.enums import ActionType
from quads.engine.validated_action import ValidatedAction
from quads.engine.money import to_cents


class ScriptedAgent:
    """
    Deterministic agent that yields a pre-defined action stream.
    Each action is a dict like: {"type": "raise", "amount": 2.0}
    Amount can be omitted for non-amounted actions.
    """

    def __init__(self, actions: list[dict], validate_action_func: Callable):
        """
        Initialize ScriptedAgent.
        
        Args:
            actions: List of action dicts with "type" and optional "amount"
            validate_action_func: Function that takes (player, action_type, amount_cents) 
                                 and returns ValidatedAction
        """
        self._iter: Iterator[dict] = iter(actions)
        self._validate_action = validate_action_func

    def decide(self, player, game_state=None) -> ValidatedAction:
        """
        Get next action from script and validate it.
        
        Args:
            player: Player object (needed for validation)
            game_state: Optional game state (not used in current validation)
            
        Returns:
            ValidatedAction object
            
        Raises:
            RuntimeError: If script runs out of actions
        """
        step = next(self._iter, None)
        if step is None:
            raise RuntimeError("ScriptedAgent ran out of actions.")

        # Parse action type
        action_type_str = step["type"]
        match action_type_str:
            case "check":
                action_type = ActionType.CHECK
            case "fold":
                action_type = ActionType.FOLD
            case "call":
                action_type = ActionType.CALL
            case "raise":
                action_type = ActionType.RAISE
            case "bet":
                action_type = ActionType.RAISE  # bet becomes raise in your system
            case _:
                raise ValueError(f"Unknown action type: {action_type_str}")

        # Convert amount to cents if present
        amount_dollars = step.get("amount")
        amount_cents = to_cents(amount_dollars) if amount_dollars is not None else 0

        # Use existing validation logic
        return self._validate_action(player, action_type, amount_cents)