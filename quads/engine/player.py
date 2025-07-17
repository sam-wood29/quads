from typing import Optional, Tuple
from quads.deuces import Card
from quads.engine.logging_utils import setup_logger

log = setup_logger(__name__)

class Player:
    """
    Represents a player in the game.
    """
    def __init__(self, 
                 id: Optional[int] = None,
                 name: Optional[str] = None,
                 stack: float = 0.0, 
                 is_bot: bool = False, 
                 seat_index: int = -1, # Unassigned until seated 
                 has_folded: bool = False,
                 has_acted: bool = False,
                 all_in: bool = False,
                 current_bet: float = 0.0,
                 controller = None,
                 pot_contrib: float = 0.0,
                 is_playing: bool = True,
                 hole_cards: Optional[Tuple[Card, Card]] = None
            ):
        """
        Initialize a player.
        """
        self.id = id
        self.name = name
        self.stack = stack
        self.is_bot = is_bot
        self.seat_index = seat_index
        self.has_folded = has_folded
        self.is_playing = is_playing
        self.pot_contrib = pot_contrib
        self.has_acted = has_acted
        self.all_in = all_in
        self.current_bet = current_bet
        self.hole_cards = hole_cards
        self.controller = controller
        self.position: Optional[str] = None
        # log.debug(f"Initialized Player: {self.__dict__}")

    def __str__(self):
        return (self.name, self.position, self.stack, self.pot_contrib, self.has_acted, self.has_folded)

    def reset_for_new_hand(self):
        """
        Reset player attributes for a new hand.
        
        Updates the following values:
            - has_folded: Reset to False
            - current_bet: Reset to 0.0
            - pot_contrib: Reset to 0.0
            - hole_cards: Reset to None (will be dealt by Hand class)
        """
        self.has_folded = False
        self.current_bet = 0.0
        self.pot_contrib = 0.0
        self.hole_cards = None  # Will be dealt by Hand class