from collections import deque
from dataclasses import dataclass


@dataclass
class PlayerState:
    id: int
    name: str
    stack: float
    position: str
    hole_cards: list[str] | None
    has_folded: bool
    is_all_in: bool
    current_bet: float
    round_contrib: float
    hand_contrib: float

@dataclass
class GameState:
    hand_id: int
    phase: str
    pot: float
    community_cards: list[str]
    players: list[PlayerState]
    action_on: int # player id of the next player to act
    last_action: dict | None = None
    min_raise: float = 0.0
    max_raise: float = 0.0
    small_blind: float = 0.0
    big_blind: float = 0.0
    dealer_position: str = ''
    
    # Phase controller fields
    street_number: int = 0
    game_session_id: int = 0
    step_number: int = 1
    
    # Street-scoped variables (reset each betting round)
    highest_bet: float = 0.0
    last_raise_increment: float = 0.0
    last_aggressor_seat: int | None = None
    acted_this_round: dict[int, bool] = None
    committed_this_round: dict[int, float] = None
    actionable_seats: deque = None
    awarded_uncontested: bool = False
    
    def __post_init__(self):
        if self.acted_this_round is None:
            self.acted_this_round = {}
        if self.committed_this_round is None:
            self.committed_this_round = {}
        if self.actionable_seats is None:
            self.actionable_seats = deque()
    
    def reset_street_vars(self, bb: float, is_preflop: bool) -> None:
        """Reset street-scoped variables for a new betting round."""
        self.highest_bet = bb if is_preflop else 0.0
        self.last_raise_increment = bb
        self.last_aggressor_seat = None
        self.acted_this_round = {p.id: False for p in self.players if not p.has_folded}
        self.committed_this_round = {p.id: 0.0 for p in self.players if not p.has_folded}
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