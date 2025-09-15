"""
Data structures for clean separation of rules, logging, and orchestration.

This module defines the data classes that flow between the different layers
of the poker engine architecture.
"""

from dataclasses import dataclass
from typing import Any

from .enums import ActionType, Phase
from .money import Cents


@dataclass(frozen=True)
class ActionDecision:
    """A player's decision about what action to take."""
    player_id: int
    action_type: ActionType
    amount: Cents
    # Additional context for the decision
    context: dict[str, Any] = None


@dataclass(frozen=True)
class AppliedAction:
    """The result of applying an action to the game state."""
    player_id: int
    action_type: ActionType
    amount: Cents
    # State before the action
    state_before: dict[str, Any]
    # State after the action  
    state_after: dict[str, Any]
    # Additional metadata
    metadata: dict[str, Any] = None


@dataclass(frozen=True)
class ValidActions:
    """Available actions for a player at a given moment."""
    player_id: int
    actions: list[ActionType]
    raise_amounts: list[Cents]
    amount_to_call: Cents
    can_check: bool
    can_bet: bool
    can_raise: bool


@dataclass(frozen=True)
class LogContext:
    """Context information for logging an action."""
    hand_id: int
    game_session_id: int
    step_number: int
    phase: Phase
    position: str
    hole_cards: str | None = None
    community_cards: str | None = None
    pot_amount: Cents = 0
    detail: str | None = None


@dataclass(frozen=True)
class GameStateSnapshot:
    """Immutable snapshot of game state for rules engine."""
    hand_id: int
    phase: Phase
    pot_cents: Cents
    community_cards: list[str]
    players: list[dict[str, Any]]  # Simplified player data
    highest_bet: Cents
    last_raise_increment: Cents
    last_aggressor_seat: int | None
    # Street-specific state
    street_number: int
    acted_this_round: dict[int, bool]
    committed_this_round: dict[int, Cents]
