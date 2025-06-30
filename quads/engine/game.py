from quads.engine.player import Player
from typing import Optional, List, Dict
from quads.engine.logging_utils import setup_logger
from quads.deuces import Deck
from random import random
from quads.engine.extras import Action, Phase, POSITIONS_BY_PLAYER_COUNT
from pprint import pformat

log = setup_logger(__name__)


class Game:
    """
    Main class for managing a game of Texas Hold'em.
    Handles player management, dealing, betting rounds, and game phases.
    """
    def __init__(self,
                 small_blind: float = 0.25,
                 big_blind: float = 0.50,
                 players: Optional[List[Player]] = None
            ):
        """
        Initialize a new game instance.
        """
        self.players: List[Player] = list()
        if players:
            self.add_player(players)
        self.community_cards = []
        self.dealer_index = 0
        self.main_pot = 0.0
        self.side_pots = []
        self.phase = Phase.WAITING
        self.action_log = []
        self.deck = Deck()
        self.small_blind = small_blind
        self.big_blind = big_blind
        self.minimum_raise = big_blind
        self.minimum_raise_inc = small_blind

    def __str__(self):
        return (
            f'phase: {self.phase}, pot: {self.pot}, dealer index: {self.dealer_index}\n' +
        "\n".join(
            f'{p.position}, {p.name}, stack: {p.stack}, seat: {p.seat_index}, folded: {p.has_folded})'
            for p in self.players
            )
        )

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

    def reset_state(self):
        '''
        resets game state for a new hand.
        '''
        self.main_pot = 0.0
        self.side_pots = []
        self.community_cards = []

        log.debug('Game State Reset')
        log.debug(self.__str__())

    def start_new_hand(self):
        """
        Start a new hand: rotate dealer, reset players, assign positions, post blinds, shuffle deck, deal hole cards, and run preflop betting.
        """
        log.debug("Starting new hand.")
        self.assign_seat_index_to_game_players()
        # hole cards are dealt here
        [p.reset_for_new_hand() for p in self.players]
        self.reset_state()
        self.assign_player_positions()
        self.post_blinds()
        
    def execute_hand(self):
        """
        Execute a full hand from start to showdown.
        """
        self.start_new_hand()
        self.run_betting_round(phase=Phase.PREFLOP, active_player_list=self.get_action_order())
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
        
        # DEBUG
        # log.debug('\nUpdated player positions:')
        # log.debug('(Name, position, seat index)')
        # for p in ordered_ap_list:
        #     log.debug(f'{p.name}, {p.position}, {p.seat_index}')

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
        # 1. Blinds are game set if None
        if sb_amount is None:
            sb_amount = self.small_blind
        if bb_amount is None:
            bb_amount = self.big_blind
        
        # 2. Get SB & BB Players
        if len(ordered_ap_list) == 2:
            bb_player = ordered_ap_list[1]
            sb_player = ordered_ap_list[0]
        else:
            sb_player = ordered_ap_list[1]
            bb_player = ordered_ap_list[2]

        # 3. Get how much Blind Players are paying
        sb_paid = min(sb_amount, sb_player.stack)
        bb_paid = min(bb_amount, bb_player.stack)

        # 4. Update the appropiate attributes
        sb_player.stack -= sb_paid
        sb_player.pot_contrib += sb_paid
        sb_player.current_bet += sb_paid
        bb_player.stack -= bb_paid
        bb_player.pot_contrib += bb_paid
        bb_player.current_bet += bb_paid

        self.pot += bb_paid + sb_paid
        # DEBUG
        # log.debug('\nposting blinds...')
        # Debugging
        # log.debug(f'pot: {self.pot}')
        # log.debug(f'{bb_player.position}, {bb_player.name}, {bb_player.stack}, {bb_player.pot_contrib}')

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

    def validate_player_action(self, acting_player, amount_to_call) -> Dict:
        '''
        Returns a dictionary with...
        - valid actions a player can take
        - valid raise/bet amounts (if applicable)
        - all-in amount
        '''
        actions = set(Action)

        # 1. forced inaction (no chips)
        if acting_player.stack <= 0:
            valid_dict = {
                'actions': [],
                'valid_raise_or_bet_amounts': [],
                'all_in_amount': 0.0
            }
        # 2. Remove illegal actions based on game state.
        if amount_to_call > 0.0:
            actions.discard(Action.CHECK)
            actions.discard(Action.BET)
        else:
            actions.discard(Action.CALL)
            actions.discard(Action.RAISE)
        
        if acting_player.stack < amount_to_call:
            actions.discard(Action.CALL)
        
        if (
            Action.RAISE in actions and
            acting_player.stack < amount_to_call + self.minimum_raise
        ):
            actions.discard(Action.RAISE)
        if (
            Action.BET in actions and 
            acting_player.stack < self.minimum_raise
        ):
            actions.discard(Action.BET)
        valid_bet_raise_amounts = []
        # 3. Build valid raise/bet amounts
        if Action.RAISE in actions or Action.BET in actions:
            min_amount = self.minimum_raise
            max_amount = acting_player.stack
            increment = self.minimum_raise_inc
            # should always be a sb
            minimum_raise = min(min_amount, max_amount)
            if minimum_raise < max_amount:
                amount = minimum_raise
                # want to seperate all in/raise & bet logically
                while amount < max_amount:
                    valid_bet_raise_amounts.append(round(amount, 2))
                    amount += increment
            else:
                valid_bet_raise_amounts.append(round(max_amount, 2))
            
        valid_dict = {
            'actions': list(actions),
            'valid_raise_or_bet_amount': valid_bet_raise_amounts,
            'all_in_amount': round(acting_player.stack, 2)
        }
        # 4. Some debugging logic
        loggable_actions = {
            k: v for k, v in valid_dict.items()
            if k in {'actions', 'all_in'}
        }

        log.debug(f'valid_actions: {pformat(loggable_actions, width=120)}')
        raise_sizes = valid_dict.get('valid_raise_or_bet_amount', [])
        num_to_show = 5
        if len(raise_sizes) > num_to_show * 2:
            summarized = raise_sizes[:num_to_show] + ['...'] + raise_sizes[-num_to_show:]
        else:
            summarized = raise_sizes
        log.debug(f'valid_raise_or_bet_amount (sample): {pformat(summarized, width=120)}')
        log.debug(f'all_in_amount: {valid_dict["all_in_amount"]}')

        # 5. return
        return valid_dict
    
    def get_action_order(self):
        """
        Returns action order for a given series of betting.
        """
        # 1. PREFLOP: Starts left of BB
        if self.phase == Phase.PREFLOP:
            bb_index = next(i for i, p in enumerate(self.players) if p.position == 'BB')
            start_index = (bb_index + 1) % len(self.players)
            log.debug(f'start index = (bb_index({bb_index}) + 1) % len players ({len(self.players)}) = {start_index}')
        # 2. FLOP/TURN/RIVER: Start left of Dealer
        else:
            dealer_index = next(i for i, p in enumerate(self.players) if p.position == 'Button')
            start_index = (dealer_index + 1) % len(self.players)
            log.debug(f'start index = (bb_index({bb_index}) + 1) % len players ({len(self.players)}) = {start_index}')
        # 3. Slice list to start with start index
        ordered = self.players[start_index:] + self.players[:start_index]
        log.debug(f'[start_index:] = players[{[p.name for p in self.players[start_index:]]}]')
        log.debug(f'[:start_index] = players[{[p.name for p in self.players[:start_index]]}]')
        log.debug(f'[ordered] = [{[(p.name, p.position) for p in ordered]}]')
        return ordered

    def run_betting_round(self, phase: Phase, active_player_list: List):
        """
        6/25 - WIP - Main utility funciton for running a betting round.

        Args:
        phase: Phase of betting round to execute
        active_player_list: list of active players within the hand:
                            Useful for logic of multiple phases. 
        """
        self.phase = phase
        action_order = self.get_action_order()
        last_raiser = None
        if self.phase == Phase.PREFLOP:
            bb_player = action_order[-1]
            amount_to_call = min(bb_player.current_bet, self.big_blind)
        else:
            amount_to_call = 0.0
        log.debug(f'amount to call: {amount_to_call}')

        players_yet_to_act = action_order.copy()
        # DEBUG
        while players_yet_to_act:
            acting_player  = players_yet_to_act.pop(0)
            # validate side pots later with player.all_in
            player_action, action_amount, last_raiser = self.get_player_action(acting_player=acting_player,
                                                             amount_to_call=amount_to_call)                                        
            
            # 6/27 -----------------------------------------------------------------------------------------

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
            
    def get_player_action(self, acting_player, amount_to_call):
        """
        6/27 - WIP - Send player state to the player controller for it to make a decision.

        Returns:
            - Action: (type): Action:
            - action_amount: (type): float:

        Future Returns:
            - p_all_in: I think I would rather it be a player attribute
            - last_raiser: This could probably be handled within the
              run betting round function.
        """

        valid_actions = self.validate_player_action(acting_player,
                                    amount_to_call)
        assert 1 == 2
        
                                    

        
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

    def assign_seat_index_to_game_players(self, rng):
        """
        Shuffles players and assigns seat indices.

        Uses optional `rng` (random number generator) parameter 
        to inject deterministic randomness for testing.

        Args:
        rng (random number generator): If None, uses default RNG.

        Updates: 
        player.seat_index
        """
        rng = rng or random
        rng.shuffle(self.players)
        for idx, player in enumerate(self.players):
            player.seat_index = idx
        # - DEBUGGING
        # player_seat_map = {player.name: player.seat_index for player in self.players}
        # log.debug(f'player name, seat_index map: \n{player_seat_map}\n')
