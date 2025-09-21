from collections import deque
from dataclasses import dataclass

from quads.engine.money import Cents


@dataclass
class PlayerState:
    id: int
    name: str
    stack: float  # Keep for backward compatibility
    position: str
    hole_cards: list[str] | None
    has_folded: bool
    is_all_in: bool
    current_bet: float  # Keep for backward compatibility
    round_contrib: float  # Keep for backward compatibility
    hand_contrib: float  # Keep for backward compatibility
    
    # MONEY: cents only - new fields for internal logic
    stack_cents: Cents = 0
    committed_cents: Cents = 0  # this hand
    current_bet_cents: Cents = 0  # this street

@dataclass
class GameState:
    hand_id: int
    phase: str
    pot: float  # Keep for backward compatibility
    community_cards: list[str]
    players: list[PlayerState]
    action_on: int # player id of the next player to act
    last_action: dict | None = None
    min_raise: float = 0.0  # Keep for backward compatibility
    max_raise: float = 0.0  # Keep for backward compatibility
    small_blind: float = 0.0  # Keep for backward compatibility
    big_blind: float = 0.0  # Keep for backward compatibility
    dealer_position: str = ''
    
    # Phase controller fields
    street_number: int = 0
    game_session_id: int = 0
    step_number: int = 1
    
    # Street-scoped variables (reset each betting round)
    highest_bet: float = 0.0  # Keep for backward compatibility
    last_raise_increment: float = 0.0  # Keep for backward compatibility
    last_aggressor_seat: int | None = None
    acted_this_round: dict[int, bool] = None
    committed_this_round: dict[int, float] = None  # Keep for backward compatibility
    actionable_seats: deque = None
    awarded_uncontested: bool = False
    
    # MONEY: cents only - new fields for internal logic
    pot_cents: Cents = 0
    bet_to_call_cents: Cents = 0
    
    def __post_init__(self):
        if self.acted_this_round is None:
            self.acted_this_round = {}
        if self.committed_this_round is None:
            self.committed_this_round = {}
        if self.actionable_seats is None:
            self.actionable_seats = deque()
    
    def reset_street_vars(self, bb: float, is_preflop: bool) -> None:  # Keep bb as float for API compatibility
        """Reset street-scoped variables for a new betting round."""
        self.highest_bet = bb if is_preflop else 0.0
        self.last_raise_increment = bb
        self.last_aggressor_seat = None
        self.acted_this_round = {p.id: False for p in self.players if not p.has_folded}
        self.committed_this_round = {p.id: 0.0 for p in self.players if not p.has_folded}
        # TODO: what is actionabe seats? why is it useful?
        self.actionable_seats.clear()
    
    def next_step_number(self) -> int:
        """Get next step number and increment."""
        current = self.step_number
        self.step_number += 1
        return current
    
    def is_seat_actionable(self, seat_id: int) -> bool:
        """Check if a seat can still act (not folded, not all-in)."""
        player = next((p for p in self.players if p.id == seat_id), None)
        if not player:
            return False
        return not player.has_folded and not player.is_all_in