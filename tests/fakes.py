from dataclasses import dataclass

from quads.engine.player import Position


@dataclass
class FakePlayerState:
    has_folded: bool = False
    is_all_in: bool = False
    bet_this_round: float = 0.0
    has_checked_this_round: bool = False


@dataclass
class FakeGameState:
    current_bet: float = 0.0
    players_by_position: dict[Position, FakePlayerState] = None
    
    def __post_init__(self):
        if self.players_by_position is None:
            self.players_by_position = {}