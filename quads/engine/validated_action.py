from dataclasses import dataclass

from quads.engine.enums import ActionType


@dataclass
class ValidatedAction:
    """Result of action validation."""
    action_type: ActionType
    amount: int
    is_full_raise: bool
    raise_increment: int
    reopen_action: bool
