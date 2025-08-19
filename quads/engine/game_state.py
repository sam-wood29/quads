from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class PlayerState:
    id: int
    name: str
    stack: float
    position: str
    hole_cards: Optional[List[str]]
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
    community_cards: List[str]
    players: List[PlayerState]
    action_on: int # player id of the next player to act
    last_action: Optional[dict] = None
    min_raise: float = 0.0
    max_raise: float = 0.0
    small_blind: float = 0.0
    big_blind: float = 0.0
    dealer_position: str = ''