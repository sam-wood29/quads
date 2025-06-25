"""
core_game.py                                            
    This file contains the core game logic for a Texas Hold'em game.                        
    It provides classes for creating a functional game of Texas Hold'em.

Classes:
    Phase: represents what stage of the hand the game is currently in
    Game: main game logic
    Player: represents a player in the game
    Position: handles position assignment
    ManualInputController: handles manual player input
"""
from typing import Optional, List, Tuple
from random import shuffle
from enum import Enum
from quads.engine.logging_utils import setup_logger
from quads.deuces import Card, Deck, Evaluator
from pprint import pformat

# Set up the project-wide logger

log = setup_logger("quads")

# Game logic supports up to ten player positions
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
        log.debug(f"Initialized Player: {self.__dict__}")

    def reset_for_new_hand(self):
        """
        6/21 - Prepares Player Attributes for a new hand.

        Adds/Updates the following values:

            -:attr:`has_folded`
            -:attr:`current_bet`
        """
        self.hole_cards = None
        self.has_folded = False
        self.current_bet = 0.0
        self.pot_contrib = 0.0
        deck = Deck()
        self.hole_cards = deck.draw(2)


class Action(Enum):
    """
    Enum representing possible player actions.
    """
    FOLD = 'fold'
    CALL = 'call'
    CHECK = 'check'
    BET = 'bet'
    RAISE = 'raise'
    


class Phase(Enum):
    """
    Enum representing the current phase of the hand.
    """
    WAITING = "waiting"
    PREDEAL = "predeal"
    PREFLOP = "preflop"
    FLOP = "flop"
    TURN = "turn"
    RIVER = "river"
    SHOWDOWN = "showdown"


class Game:
    """
    Main class for managing a game of Texas Hold'em.
    Handles player management, dealing, betting rounds, and game phases.
    """
    def __init__(self,
                 small_blind: float = 0.25,
                 big_blind: float = 0.50,
                 debug = False,
                 players: Optional[List[Player]] = None
            ):
        """
        Initialize a new game instance.
        """
        log.debug("Initializing new Game instance.")
        self.players: List[Player] = list()
        if players:
            self.add_player(players)
        self.community_cards = []
        self.dealer_index = 0
        self.pot = 0.0
        self.phase = "predeal"
        self.action_log = []
        self.deck = Deck()
        self.small_blind = small_blind
        self.big_blind = big_blind
        self.minimum_raise = big_blind
        self.minimum_raise_inc = small_blind

    def add_player(self, player_or_list):
        """
        6/21 - Adds a single player or list of players to the game.

        Adds/Updates the following values:

            - :attr:`players`
        """
        if isinstance(player_or_list, list):
            for p in player_or_list:
                self._add_single_player(p)
            log.debug(f'added players (names): {[p.name for p in self.players]}')
        else:
            self._add_single_player(player_or_list)
            log.debug(f'Adding player (name): {player_or_list.name}')
        # log.debug(Game.add_player.__doc__)

    def _add_single_player(self, player: Player):
        """
        6/21 - Adds a single player to the game.

        Adds/Updates the following values:

            - :attr:`players`
        """
        self.players.append(player)
        # log.debug(Game._add_single_player.__doc__)

    def get_action_order(self, phase: Phase) -> List[Player]:
        """
        6/22 - Might be able to depricate this by passing ordered_ap_list
        """
        log.debug(f"Getting action order for phase: {phase.name}")
        active_players = [p for p in self.players if p.is_playing and not p.has_folded]
        if len(active_players) < 2:
            return []
        if phase == Phase.PREFLOP:
            # Preflop: rotate from Big Blind using position labels
            position_list = POSITIONS_BY_PLAYER_COUNT[len(active_players)]
            bb_index = position_list.index("Big Blind")
            rotated_positions = position_list[bb_index + 1:] + position_list[:bb_index + 1]
            log.debug(f"Rotated position order: {rotated_positions}")
            ordered_players = []
            for pos in rotated_positions:
                for p in self.players:
                    if p.position == pos and p.is_playing and not p.has_folded:
                        ordered_players.append(p)
            log.debug(f"Preflop action order: {[p.name for p in ordered_players]}")
            return ordered_players
        else:
            # Postflop: act from seat left of dealer
            ordered_players = []
            n = len(self.players)
            for i in range(1, n + 1):
                idx = (self.dealer_index + i) % n
                p = self.players[idx]
                if p.is_playing and not p.has_folded:
                    ordered_players.append(p)
            log.debug(f"Postflop action order: {[p.name for p in ordered_players]}")
            return ordered_players

    def start_new_hand(self):
        """
        Start a new hand: rotate dealer, reset players, assign positions, post blinds, shuffle deck, deal hole cards, and run preflop betting.
        """
        log.debug("Starting new hand.")
        self.rotate_dealer()
        self.assign_player_positions()
        self.post_blinds()
        self.deck.shuffle()
        self.starting_player_count = len([p for p in self.players if p.is_playing])
        self.community_cards = []
        self.pot = 0.0
        self.phase = Phase.PREFLOP
        self.deal_hole_cards()
        self.run_betting_round(Phase.PREFLOP)

    def execute_hand(self):
        """
        Execute a full hand from start to showdown.
        """
        log.debug("Executing full hand.")
        self.start_new_hand()
        self.deal_flop()
        self.run_betting_round(Phase.FLOP)
        self.deal_turn()
        self.run_betting_round(Phase.TURN)
        self.deal_river()
        self.run_betting_round(Phase.RIVER)
        log.debug("Showdown (not implemented yet)")
        self.action_log.append("Showdowm occurs.")

    def rotate_dealer(self):
        """
        Rotate the dealer to the next active player.
        """
        n = len(self.players)
        for i in range(1, n + 1):
            next_index = (self.dealer_index + i) % n
            if self.players[next_index].is_playing:
                self.dealer_index = next_index
                log.debug(f"Dealer rotated to seat {self.dealer_index}")
                break

    def assign_player_positions(self) -> List[Player]:
        """
        6/21 - Modifies each active players position

        Updates the following values:
            - :attr:`.Player.positon`

        Returns: 
            - list: Ordered list of active players, starting with the button.
        """
        active_players = [p for p in self.players if p.is_playing]
        num_active = len(active_players)
        if num_active < 2:
            raise ValueError('At least 2 players are needed to play a hand.')
        if num_active > 10:
            raise ValueError('More than 10 players not supported.')
        positions_by_count = POSITIONS_BY_PLAYER_COUNT[num_active]
        seat_to_player_map = {p.seat_index: p for p in active_players}
        ordered_seats = []
        for i in range(num_active):
            seat = (self.dealer_index + i) % num_active
            if seat in seat_to_player_map:
                ordered_seats.append(seat)
        # ordered seats = the ordred seat indexes with the dealer being [0]
        # used to implement position order
        ordered_ap_list = []
        for idx, seat_index in enumerate(ordered_seats):
            player = seat_to_player_map[seat_index]
            player.position = positions_by_count[idx]
            ordered_ap_list.append(player)
        
        log.debug('\nUpdated player positions:')
        log.debug('(Name, position, seat index)')
        for p in ordered_ap_list:
            log.debug(f'{p.name}, {p.position}, {p.seat_index}')

        # log.debug(Game.assign_player_positions.__doc__)
        # Returning this to cut out on logic down the road?
        return ordered_ap_list

    def post_blinds(self, 
                    ordered_ap_list,
                    sb_amount=None,
                    bb_amount=None):
        """
        6/21 - Posts SB & BB for the hand.

        Args:
            - ordered_ap_list: ordered list of active players starting with the button
            - sb_amount: defaults to game attribute
            - bb_amount: defaults to game attribute

        Updates:
            - self.pot
            - sb & bb player attributes

        Returns:
            None
        """
        # double blinds or something in the future.
        if sb_amount is None:
            sb_amount = self.small_blind
        if bb_amount is None:
            bb_amount = self.big_blind

        if len(ordered_ap_list) == 2:
            bb_player = ordered_ap_list[1]
        else:
            sb_player = ordered_ap_list[1]
            bb_player = ordered_ap_list[2]

        sb_player.stack -= sb_amount
        sb_player.pot_contrib += sb_amount
        bb_player.stack -= bb_amount
        bb_player.pot_contrib += bb_amount

        self.pot += bb_amount + sb_amount
        log.debug('\nposting blinds...')
        log.info('Will need to update tracking here?')
        # Debugging
        log.debug(f'pot: {self.pot}')
        if sb_player:
            log.debug(f'{sb_player.position}, {sb_player.name}, {sb_player.stack}, {sb_player.pot_contrib}')
        log.debug(f'{bb_player.position}, {bb_player.name}, {bb_player.stack}, {bb_player.pot_contrib}')

    def deal_hole_cards(self):
        
        """
        Deal two hole cards to each active player.
        MIGHT BE DEPRICATED 6/22
        """
        log.debug("Dealing hole cards to players.")
        for player in self.players:
            if player.is_playing:
                player.hole_cards = tuple(self.deck.deal(2))
                self.action_log.append(f"{player.name} is dealt hole cards.")
                log.debug(f"{player.name} is dealt hole cards: {player.hole_cards}")

    def get_call_amount(self, player: Player) -> float:
        """
        Returns how much the player needs to call to match the highest current bet.
        """
        highest_bet = max(p.current_bet for p in self.players if p.is_playing and not p.has_folded)
        call_amt = max(0.0, highest_bet - player.current_bet)
        log.debug(f"Call amount for {player.name}: {call_amt}")
        return call_amt

    def deal_flop(self):
        """
        Deal the flop (three community cards).
        """
        log.debug("Dealing flop.")
        self.deck.burn()
        self.community_cards.extend(self.deck.deal(3))
        self.phase = Phase.FLOP
        log.debug(f"Flop: {self.community_cards}")

    def deal_turn(self):
        """
        Deal the turn (fourth community card).
        """
        log.debug("Dealing turn.")
        self.deck.burn()
        self.community_cards.append(self.deck.deal(1)[0])
        self.phase = Phase.TURN
        log.debug(f"Turn: {self.community_cards[-1]}")

    def deal_river(self):
        """
        Deal the river (fifth community card).
        """
        log.debug("Dealing river.")
        self.deck.burn()
        self.community_cards.append(self.deck.deal(1)[0])
        self.phase = Phase.RIVER
        log.debug(f"River: {self.community_cards[-1]}")

    def validate_player_action(self, amount):
        player1 = self.players[0]
        log.debug(player1.name)

    def run_betting_round(self, phase: Phase, ordered_ap_list: List):
        """
        6/22 - WIP - Full logic for running a betting round.

        Args:
        - ordered_ap_list: ordered list of active players (starting index may very by phase?)
        - phase: phase of the hand
        """
        # New hopefully improved version of this...
        log.debug('\nDEBUG ------------ run betting round ------------\n')
        self.phase = phase
        remaining_players = len(ordered_ap_list)
        log.debug(f'remaining_players: {remaining_players}')
        log.debug('\nOrdered ap list\n')
        # DEBUG
        for p in ordered_ap_list:
            log.debug(f'name: {p.name}, has_acted: {p.has_acted}, position {p.position}')

        log.debug('\nCreating action order list...\n')
        
        log.debug(f'Ordered active player list before rotation: {[(p.name, p.position) for p in ordered_ap_list]}')
        if self.phase == Phase.PREFLOP and remaining_players > 2:
            bb_player = ordered_ap_list[2]
            log.debug(f'bb_player name: {bb_player.name}')
            ordered_ap_list = ordered_ap_list[-2:] + ordered_ap_list[:-2]
            log.debug('More than two players')
            log.debug(f'Ordered active player list: after rotation{[(p.name, p.position) for p in ordered_ap_list]}\n')
            
        if self.phase == Phase.PREFLOP and remaining_players == 2:
            bb_player = ordered_ap_list[1]
            ordered_ap_list = ordered_ap_list[-1:] + ordered_ap_list[:-1]
            log.debug('two players\n\n')
            log.debug(f'Ordered active player list: {[(p.name, p.position) for p in ordered_ap_list]}')

        last_raiser = None
        
        log.debug(f'bb_player: {bb_player.name}, pot_contrib: {bb_player.pot_contrib}')

        call_amount = bb_player.pot_contrib
        log.debug(f'call_amount: {call_amount}')
        players_yet_to_act = ordered_ap_list.copy()
        # DEBUG
        for p in ordered_ap_list:
            log.debug(f'{p.name}, {p.position}, {p.has_acted}')
        
        
        while players_yet_to_act:
            acting_p  = players_yet_to_act.pop(0) # 'acting player'


            # Going to pass this in so that AI/controller has a set of answers to work with.
            # valid_actions = self.get_valid_actions(player, call_amount, min_raise, max_raise)


            p_action, action_amount, p_all_in, last_raiser = self.get_player_action(player=acting_p,
                                                             call_amount=call_amount) # This function needs be checked
                                                             
            match p_action:
                case 'fold':
                    acting_p.has_folded = True
                case 'check':
                    continue # Need some logging here maybe
                case 'call':
                    # This is fine, we can work on the logic to return
                    # how much the action_amount_and whether the player
                    # is all in or not later
                    acting_p.stack -= action_amount
                    acting_p.pot_contrib += action_amount
                    self.pot += action_amount
                case 'raise':
                    # raise amount in this case is 'raise_by amount'
                    raise_amount = action_amount
                    total_bet = raise_amount + call_amount
                    acting_p.stack -= total_bet
                    self.pot += total_bet
                    last_raiser = acting_p

                    # Rebuild yet to act:
                    last_raiser_index = ordered_ap_list.index(last_raiser)
                    log.debug(f'last raiser name: {last_raiser.name}, index: {last_raiser_index}')

                    players_yet_to_act = []
                    for i in range(len(ordered_ap_list) - 1):
                        idx = (last_raiser_index + 1 + i) % len(ordered_ap_list)
                        player = ordered_ap_list[idx]
                        log.debug(f'player: {player.name}, {player.position}, {player.has_folded}')
                        if player.has_folded or (player.stack <= 0) or player.all_in:
                            continue
                        else:
                            players_yet_to_act.append(player)
                    log.debug(f'players yet to act{[(p.name, p.position) for p in players_yet_to_act]}')

                case _:
                    raise ValueError('Invalid action')
                
            
            # Here DEBUG block just to know wtf is going on
            

        




        
    def get_player_action(self, player, call_amount):
        """
        6/22 - WIP - Send player state to the player controller for it to make a decision.

        Returns:
            - Action: (type): Enum: e.g., Action.FOLD, ACTION.RAIASE.
            - action_amount: (type): float: for example the raise amount.

        Future Returns:
            - p_all_in: I think I would rather it be a player attribute
            - last_raiser: This could probably be handled within the
              run betting round function.
        """
        
        
        self.validate_player_action(player, call_amount)

        
        game_state = {
            "phase": self.phase,
            "pot": self.pot,
            "call_amount": call_amount,
            "community_cards": self.community_cards,
            "minimum_raise": self.minimum_raise
        }
        # return player.controller.decide(player, game_state)

    def show_community_cards(self):
        """
        Return a string representation of the community cards.
        """
        return ' '.join(str(card) for card in self.community_cards)

    def end_hand_cleanup(self):
        """
        Reset player bets at the end of a hand.
        """
        log.debug("Cleaning up at end of hand.")
        for player in self.players:
            player.current_bet = 0
        log.debug("Player bets reset.")

    def assign_seat_seat_index_to_game_players(self):
        """
        6/21 - Shuffles all players in the game, then assigns seat indexs based on order.

        Adds/Updates the following values:
            - :attr:`seat_index`
        """
        shuffle(self.players)
        for idx, player in enumerate(self.players):
            player.seat_index = idx

        # - DEBUGGING
        player_seat_map = {player.name: player.seat_index for player in self.players}
        log.debug(f'player name, seat_index map: \n{player_seat_map}\n')

    

class Position:
    """
    Helper class for assigning position names to players based on seat index and button location.
    """
    def __init__(self, num_players: int):
        """
        Initialize with the number of players.
        """
        if not (2 <= num_players <= 10):
            raise ValueError("Only 2 to 10 players supported.")
        self.positions = POSITIONS_BY_PLAYER_COUNT[num_players]
        log.debug(f"Position helper initialized for {num_players} players: {self.positions}")

    def get_position(self, seat_index: int, button_index: int) -> str:
        """
        Given a seat_index and the button's index, return the official position name.
        """
        offset = (seat_index - button_index) % len(self.positions)
        pos = self.positions[offset]
        log.debug(f"Seat {seat_index} with button at {button_index} is position {pos}")
        return pos
        


class ManualInputController:
    """
    Controller for manual (human) player input via the terminal.
    """
    def decide(self, player, game_state) -> Tuple[Action, Optional[float]]:
        """
        Prompt the user for an action and return it.
        """
        print(f"\n--- {player.name}'s Turn ---")
        print(f"\nPhase: {game_state['phase'].name}")
        print(f"Stack Amount: {player.stack:.2f}")
        print(f"Current bet to call: {game_state['call_amount']:.2f}")
        print(f"Pot size: {game_state['pot']:.2f}")
        print(f"Community cards: {' '.join(str(c) for c in game_state['community_cards'])}")
        print("Player's cards: ", ' '.join(str(c) for c in player.hole_cards), "\n")
        log.debug(f"ManualInputController: {player.name} deciding action with state {game_state}")
        valid_actions = ["fold","call","check","raise"]
        while True:
            raw = input("Choose action (e.g., 'call', 'raise 120', 'check', 'fold', 'all in')\n").strip().lower()
            parts = raw.split()
            if not parts:
                print("Empty input. Try again.")
                continue
            action = parts[0]
            if action == "fold":
                return(Action.FOLD, None)
            elif action == "call":
                return (Action.CALL, None)
            elif action == "check":
                if game_state["call_amount"] == 0:
                    return (Action.CHECK, None)
                else:
                    print("You cannot check - there is a bet to call.")
                    continue
            elif action == "raise":
                if len(parts) != 2:
                    print("Usage: raise [amount]")
                    continue
                try:
                    amount = float(parts[1])
                    if amount < game_state["minimum_raise"]:
                        print(f"Raise must be at least {game_state['minimum_raise']}.")
                        continue
                    return (Action.RAISE, amount)
                except ValueError:
                    print("Invalid raise amount.")
                    continue
            # Going to get rid of this
            elif action == "all_in":
                return (Action.RAISE, player.stack)
            else:
                print("Unrecognized action. Try again.")


