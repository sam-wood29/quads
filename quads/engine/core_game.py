from typing import List, Optional
from quads.deuces import Deck, Card
from enum import Enum
from random import shuffle
from pprint import pprint, pformat
from quads.engine.logging_utils import setup_logger

smoke = setup_logger(name=__name__,
             log_file='logs/smoke.log',
             mode='a')

class Player:
    def __init__(self,
                 stack: float = 100,
                 is_bot: bool = False,
                 controller = None,
                 name: Optional[str] = None,
                 seat_index: Optional[int] = None,
                 hole_cards: Optional[List[Card]] = None
                 ):
        self.stack = stack
        self.is_bot = is_bot
        self.controller = controller
        self.name = name
        self.seat_index = seat_index
        self.hole_cards = hole_cards

    def __str__ (self):
        return (
            f'name: {self.name}\n'
            f'hole cards: {Card.compact_cards_str(self.hole_cards)}\n'
            f'position: {self.position}, seat_index: {self.seat_index}\n'
            f'in hand: {self.in_hand}, has acted: {self.has_acted}, all in: {self.all_in}\n'
            f'pot contribution {self.pot_contrib}'
        )

class Phase(Enum):
    PLAYING = "playing"
    WAITING = "waiting"
    PREFLOP = "preflop"
    FLOP = "flop"
    TURN = "turn"
    RIVER = "river"
    SHOWDOWN = "showdown"

POSITIONS_BY_PLAYER_COUNT = {
    2: ["Button", "BB"],
    3: ["Button", "SB", "BB"],
    4: ["Button", "SB", "BB", "UTG"],
    5: ["Button", "SB", "BB", "UTG", "CO"],
    6: ["Button", "SB", "BB", "UTG", "HJ", "CO"],
    7: ["Button", "SB", "BB", "UTG", "MP", "HJ", "CO"],
    8: ["Button", "SB", "BB", "UTG", "UTG+1", "MP", "HJ", "CO"],
    9: ["Button", "SB", "BB", "UTG", "UTG+1", "UTG+2", "MP", "HJ", "CO"],
    10: ["Button", "SB", "BB", "UTG", "UTG+1", "UTG+2", "MP", "LJ", "HJ", "CO"]
}

class Game:
    def __init__ (self,
                  players = List[Player]
                  ):
        self.hands: List[Hand] = []
        self.players = players
        self.phase = Phase.WAITING
        self.deck = Deck()
        self.dealer_index = -1 # starts before the first hand

    def assign_players_ingame_new_seats(self):
        """Assigns seats to all players initialized within a game"""
        shuffle(self.players)
        for player in self.players:
            player.seat_index = self.players.index(player)
    
    # Going to move this over to the hand class.
    def assign_player_positions_for_hand(self):
        """Assigns player positons based on game.player.seat_index and offset
           from game.dealer_index offset."""
        self.players.sort(key=lambda player: player.seat_index)
        total_players = len(self.players)
        positions = POSITIONS_BY_PLAYER_COUNT[total_players]
        for player, position in zip(self.players, positions):
            player.position = position
    
    def play_hand(self):
        """Create and play a hand of TH."""
        # rotate the dealer before playing the hand
        self.dealer_index = (self.dealer_index + 1) % len(self.players)

        hand = Hand(players=self.players,
                    deck=self.deck,
                    dealer_index=self.dealer_index)

        smoke.info(f'hand index: {len(self.hands)}')
        self.hands.append(hand)
        hand.play()


class Hand:
    def __init__ (self,
                  players: List[Player],
                  deck: Deck,
                  dealer_index: int,
                  small_blind: float = 0.25,
                  big_blind: float = 0.50):
        """Represents a hand of TH"""
        self.players = players
        self.deck = deck
        self.dealer_index = dealer_index
        self.small_blind = small_blind
        self.big_blind = big_blind
        self.min_raise = big_blind
        self.min_raise_inc = small_blind
        self.community_cards = List[Card]
        self.pot: float = 0.0
    
    def __str__(self):
        return (
            f'pot: {self.pot}'
        )
    
    def prepare_for_new_hand(self):
        """Prepares gamestate for a newhand."""
        smoke.info('hand.prepare_for_new_hand()')
        self.phase = Phase.PREFLOP
        self.pot = 0.0

        for player in self.players:
            player.hole_cards = self.deck.draw(2)
            player.in_hand = True
            player.pot_contrib = 0.0 # Amount of chips contributed to a pot by player in current hand.
            player.has_acted = False
            player.all_in = False

            smoke.info(player.__str__())
        
        smoke.info(f'hand.phase: {self.phase}')
        smoke.info(f'hand.pot: {self.pot}')

    
    def _display_button_new_hand(self):
        """utility funciton to print the statistics for
           self.prepare_for_new_hand function to make sure it is working."""
        

    def execute_betting_round(self, dealer_index, phase):
        """Executes a betting round of TH.
           For instance preflop, or river."""

    def execute_non_showdown_winner(self, winning_player):
        """Executes logic for when a player wins a hand before showdown."""

    
    def execute_showdown(self, players_showing):
        """Executes showdown calculations."""
        # pass in players in order of last who needs to show first/last
        # should make it easier to implement.
    
    def play(self):
        """Play a hand of TH."""
        self.prepare_for_new_hand()
        self.phase = Phase.PREFLOP
        self.execute_betting_round(dealer_index=self.dealer_index,
                                   phase=self.phase)
