"""
hand.py

Hand class for managing a single hand of Texas Hold'em.
This class encapsulates all logic and state for one complete hand.
"""
from typing import List, Dict, Optional, Tuple
from quads.deuces import Card, Deck, Evaluator
from quads.engine.extras import Action, Phase, POSITIONS_BY_PLAYER_COUNT
from quads.engine.logging_utils import setup_logger
from quads.engine.player import Player
from pprint import pformat
import math
import logging


class Hand:
    """
    Represents a single hand of Texas Hold'em.
    Manages dealing, betting rounds, showdown, and pot distribution.
    """
    
    def __init__(self, 
                 players: List[Player],
                 small_blind: float = 0.25,
                 big_blind: float = 0.50,
                 dealer_index: int = 0,
                 logger: Optional[logging.Logger] = None,
                 hand_id: Optional[str] = None,
                 min_raise: Optional[float] = None,
                 max_raise: Optional[float] = None,
                 betting_increments: str = 'none'):
        """
        Initialize a new hand.
        
        Args:
            players: List of Player objects participating in this hand
            small_blind: Small blind amount
            big_blind: Big blind amount  
            dealer_index: Seat index of the dealer
            logger: Logger instance for this hand
            hand_id: Unique identifier for this hand
            min_raise: Minimum raise amount (defaults to big blind for unopened pots)
            max_raise: Maximum raise amount (None for no limit)
            betting_increments: Betting increment rule ('none', 'big_blind', 'small_blind')
        """
        self.players = players
        self.small_blind = small_blind
        self.big_blind = big_blind
        self.dealer_index = dealer_index
        self.logger = logger or setup_logger(f"hand_{hand_id}" if hand_id else "hand")
        self.logger.setLevel(logging.DEBUG)
        self.hand_id = hand_id
        
        # Betting structure
        self.min_raise = min_raise  # Custom min raise (None = use big blind)
        self.max_raise = max_raise  # None for no limit
        self.betting_increments = betting_increments  # 'none', 'big_blind', 'small_blind'
        self.last_raise_increment = 0  # Track last raise for min-raise rule
        self.current_round_raises = []  # Track all raises in current round
        
        # Hand state
        self.deck = Deck()
        self.community_cards = []
        self.pot = 0.0
        self.side_pots = []
        self.phase = Phase.PREDEAL
        self.action_log = []  # Structured log for ML/analysis
        
        # Player state tracking
        self.start_stacks = {p: p.stack for p in players}
        self.active_players = [p for p in players if p.is_playing]
        
        # Position and betting state
        self.positions_assigned = False
        self.blinds_posted = False
        
    def play(self) -> Dict:
        """
        Play a complete hand from start to finish.
        
        Returns:
            Dict containing hand results (winners, pot distribution, etc.)
        """
        
        try:
            self._reset_players()
            self._assign_positions()
            self._post_blinds()
            self._deal_hole_cards()
            
            # Run betting rounds
            self._run_betting_round(Phase.PREFLOP)
            if self._should_continue():
                self._deal_flop()
                self._run_betting_round(Phase.FLOP)
                
            if self._should_continue():
                self._deal_turn()
                self._run_betting_round(Phase.TURN)
                
            if self._should_continue():
                self._deal_river()
                self._run_betting_round(Phase.RIVER)
            
            # Showdown or award pot
            if self._should_showdown():
                return self._showdown()
            else:
                return self._award_pot_to_last_player()
                
        except Exception as e:
            self.logger.error(f"Error during hand play: {e}")
            raise

    def _reset_players(self):
        """Reset all players for a new hand."""
        for player in self.players:
            player.reset_for_new_hand()
        self.active_players = [p for p in self.players if p.is_playing]

    def _assign_positions(self):
        """Assign positions to players based on dealer index."""
        self.logger.info("=== Player Positions ===")
        
        # Get players who are playing
        active_players = [p for p in self.players if p.is_playing]
        num_active = len(active_players)
        
        if num_active < 2:
            raise ValueError("Not enough players to assign positions")
        if num_active > 10:
            raise ValueError("Too many players to assign positions")
        
        # Get position names for number of active players
        position_names = POSITIONS_BY_PLAYER_COUNT[num_active]
        
        # Create a map: seat_index -> player object
        seat_to_player_map = {p.seat_index: p for p in active_players}
        
        # Calculate seat order starting from the dealer
        seats_in_order = []
        for i in range(num_active):
            seat = (self.dealer_index + i) % num_active
            if seat in seat_to_player_map:
                seats_in_order.append(seat)
        
        # Assign positions to players in order
        players_in_position_order = []
        for idx, seat_index in enumerate(seats_in_order):
            player = seat_to_player_map[seat_index]
            player.position = position_names[idx]
            players_in_position_order.append(player)
            self.logger.info(f"Player: '{player.name}' -> Position: {player.position}")
        self.logger.info('=========================\n')
        
        # for use of blinds, betting, etc.        
        self.players_in_position_order = players_in_position_order
        self.positions_assigned = True

    def _post_blinds(self, sb_amount=None, bb_amount=None):
        """Post small and big blinds."""
        if not hasattr(self, 'players_in_position_order'):
            raise RuntimeError("Positions must be assigned before posting blinds.")
        if sb_amount is None:
            sb_amount = self.small_blind
        if bb_amount is None:
            bb_amount = self.big_blind

        players_in_position_order = self.players_in_position_order
        if len(players_in_position_order) == 2:
            bb_player = players_in_position_order[1]
            sb_player = players_in_position_order[0]
        else:
            sb_player = players_in_position_order[1]
            bb_player = players_in_position_order[2]

        sb_paid = min(sb_amount, sb_player.stack)
        bb_paid = min(bb_amount, bb_player.stack)

        sb_player.stack -= sb_paid
        sb_player.pot_contrib += sb_paid
        sb_player.current_bet += sb_paid
        bb_player.stack -= bb_paid
        bb_player.pot_contrib += bb_paid
        bb_player.current_bet += bb_paid

        self.pot += bb_paid + sb_paid
        
        self.blinds_posted = True

    def _deal_hole_cards(self):
        """Deal two hole cards to each active player."""
        for player in self.active_players:
            player.hole_cards = tuple(self.deck.draw(2))

    def _deal_flop(self):
        """Deal the flop (three community cards)."""
        self.deck.draw(1)  # Burn card
        self.community_cards = self.deck.draw(3)
        self.phase = Phase.FLOP

    def _deal_turn(self):
        """Deal the turn (fourth community card)."""
        self.logger.debug("Dealing turn")
        self.deck.draw(1)  # Burn card
        self.community_cards.append(self.deck.draw(1))
        self.phase = Phase.TURN

    def _deal_river(self):
        """Deal the river (fifth community card)."""
        self.logger.debug("Dealing river")
        self.deck.draw(1)
        self.community_cards.append(self.deck.draw(1))
        self.phase = Phase.RIVER

    def _get_preflop_action_order(self):
        num_players = len(self.players_in_position_order)
        if num_players == 2:
            # Heads-up: Button acts first preflop, then BB
            action_order = [
                next(p for p in self.players_in_position_order if p.position == "Button"),
                next(p for p in self.players_in_position_order if p.position == "BB"),
            ]
        else:
            first_to_act = 3 % num_players
            action_order = self.players_in_position_order[first_to_act:] + self.players_in_position_order[:first_to_act]
        return action_order

    def _get_postflop_action_order(self):
        num_players = len(self.players_in_position_order)
        if num_players == 2:
            # Postflop: BB acts first, Button acts last
            action_order = [
                next(p for p in self.players_in_position_order if p.position == "BB"),
                next(p for p in self.players_in_position_order if p.position == "Button"),
            ]
        else:
            first_to_act = (self.players_in_position_order.index(
                next(p for p in self.players_in_position_order if p.position == "Button")
            ) + 1) % num_players
            action_order = self.players_in_position_order[first_to_act:] + self.players_in_position_order[:first_to_act]
        return action_order

    def _run_betting_round(self, phase: Phase):
        """Run a simple betting round for the given phase."""
        self.phase = phase
        self._reset_betting_state()

        # Determine action order
        if phase == Phase.PREFLOP:
            action_order = self._get_preflop_action_order()
        else:
            action_order = self._get_postflop_action_order()
        self.logger.debug(f'action order...')
        # for p in action_order:
        #     self.logger.debug(f'{p.name} {p.position}')

        # Print initial state for this betting round
        self.logger.info(f'                                                                                    {phase.name.capitalize()}')
        self.logger.info(f'-----------------------------------------------------------------------------------------------')
        self._print_game_state_debug()

        for player in action_order:
            player.has_acted = False  # Track if player has acted this round

        highest_bet = max(p.current_bet for p in action_order)
        players_yet_to_act = [p for p in action_order if not p.has_folded and p.stack > 0]

        while players_yet_to_act:
            player = players_yet_to_act.pop(0)
            if player.has_folded or player.stack == 0:
                continue
            # Calculate amount to call
            amount_to_call = highest_bet - player.current_bet

            # Get valid actions
            valid_actions = self._get_valid_actions(player, amount_to_call, highest_bet)
            
            # Pass valid actions to controller
            game_state = self._get_game_state(player, amount_to_call)
            game_state['valid_actions'] = valid_actions

            # Ask controller for action
            action, amount = player.controller.decide(player, game_state)
            
            # Validate action
            if not self._validate_action(action, amount, valid_actions, player, highest_bet):
                self.logger.error(f"Invalid action {action} with amount {amount} from {player.name}")
                action, amount = self._handle_invalid_action(player, valid_actions)

            # Apply action
            if action == Action.FOLD:
                player.has_folded = True
                self.logger.debug(f"{player.name} folds.")
                total_bet = None
            elif action == Action.CALL or (action == Action.CHECK and amount_to_call == 0):
                call_amt = min(amount_to_call, player.stack)
                player.stack -= call_amt
                player.current_bet += call_amt
                player.pot_contrib += call_amt
                self.pot += call_amt
                self.logger.debug(f"Call: player={player.name}, amount_to_call={amount_to_call}, call_amt={call_amt}, pot={self.pot}")
                
                self.logger.debug(f"{player.name} {'calls' if action == Action.CALL else 'checks'} {call_amt}.")
                self.logger.info(f"Pot after {player.name if player else 'system'} {action}: {self.pot}")
                self._print_game_state_debug(player, action, call_amt)
                total_bet = None
            elif action == Action.RAISE or Action.BET:
                # For simplicity, treat amount as the total bet (not just the raise increment)
                total_bet = amount 
                additional_bet = total_bet - player.current_bet
                player_bet_increment = min(additional_bet, player.stack)
                
                previous_highest_bet = highest_bet  # Save before updating
                player.stack -= player_bet_increment
                player.current_bet += player_bet_increment
                player.pot_contrib += player_bet_increment
                self.pot += player_bet_increment
                highest_bet = player.current_bet
                
                # Player should not be able to raise if cannot cover, therefore I do not 
                # Update last raise amount if the player covers. this block is confusing
                # Only update last_raise_amount if this is a full raise (not an all-in for less)
                if player_bet_increment == (total_bet - player.current_bet + player_bet_increment):  # Player covered the full raise
                    self.last_raise_increment = total_bet - previous_highest_bet
                # Otherwise, do not update last_raise_amount (all-in for less)
                self.current_round_raises.append(self.last_raise_increment)
                
                self.logger.debug(f"{player.name} raises to {player.current_bet}.")
                self.logger.debug(f"Raise amount: {additional_bet}, last_raise_amount: {self.last_raise_increment}")
                
                # Rebuild using the original action order, but reorder to continue from next player
                remaining_players = [
                    p for p in action_order
                    if not p.has_folded and p.stack > 0 and p != player and p.current_bet < highest_bet
                ]
                
                # Find the index of the current player in the original action order
                raiser_index = action_order.index(player)
                
                # Reorder so action continues from the next player after the raiser
                players_yet_to_act = []
                for i in range(len(action_order)):
                    check_index = (raiser_index + 1 + i) % len(action_order)
                    check_player = action_order[check_index]
                    if check_player in remaining_players:
                        players_yet_to_act.append(check_player)
            
            else:
                # logic for 'Bet' is unknown. it in theory is the same as 'Raise', but first.
                self.logger.warning(f"Unknown action {action} from {player.name}")

            player.has_acted = True
            self._debug_player_action(player=player, action=action, amount_to_call=amount_to_call, 
                                      total_bet=total_bet,
                                      highest_bet=highest_bet)
            
            self.logger.debug(f"\nplayers yet to act: {[p.name for p in players_yet_to_act]}")
            self.logger.debug(f"pot: ${self.pot}")
            contributions = [f"{p.name}: ${p.pot_contrib:.2f}" for p in self.players_in_position_order if p.pot_contrib > 0]
            if contributions:
                self.logger.info(f"Contributions: {', '.join(contributions)}")
            

            # End round if only one player remains
            active_players = [p for p in self.players_in_position_order if not p.has_folded and p.stack > 0]
            if len(active_players) == 1:
                self.logger.debug("Only one player remains ({active_players[0].name} wins!), ending betting round.")
                break

        # Reset current_bet for all players for the next round
        for player in self.players_in_position_order:
            player.current_bet = 0
    
    def _debug_player_action(self, player, action, amount_to_call, highest_bet, total_bet):
        self.logger.debug(f"\n--- {player.name}'s action ---")
        match action:
            case Action.FOLD:
                self.logger.debug(f"{player.name} folds")
            case Action.CHECK:
                self.logger.debug(f"{player.name} checks")
            case Action.CALL:
                self.logger.debug(f"{player.name} calls raise of ${highest_bet}; (${amount_to_call} more)")
            case Action.RAISE:
                self.logger.debug(f"{player.name} raises to {total_bet}")
            case _:
                raise ValueError('Unsupported Action')
        self.logger.debug(f"\n--- {player.name}'s state ---")
        summary_dict = player._get_summary_helper()
        self.logger.debug(pformat(summary_dict, width=20))

    def _should_continue(self) -> bool:
        """Check if the hand should continue to the next street."""
        active_players = [p for p in self.active_players if not p.has_folded]
        return len(active_players) > 1

    def _should_showdown(self) -> bool:
        """Check if a showdown should occur."""
        active_players = [p for p in self.active_players if not p.has_folded]
        return len(active_players) > 1

    def _showdown(self) -> Dict:
        """Determine winners and distribute pot."""
        self.phase = Phase.SHOWDOWN
        phase = self.phase
        self.logger.info(f'                                                                                    {phase.name.capitalize()}')
        self.logger.info(f'-----------------------------------------------------------------------------------------------')

        # 1. Get all players who haven't folded
        eligible_players = [p for p in self.players_in_position_order if not p.has_folded]

        # 2. Evaluate each player's hand
        evaluator = Evaluator()
        showdown_dict = {}
        for player in eligible_players:
            score = evaluator.evaluate(list(player.hole_cards), list(self.community_cards))
            class_rank = evaluator.get_rank_class(score)
            hand_name = evaluator.class_to_string(class_rank)
        
            showdown_dict[player] = {
                'score': score,
                'hand_name': hand_name,
                'class_rank': class_rank
            }    
            self.logger.debug(f'{player.name}: score: {score}, hand name: {hand_name}, hand_class rank {class_rank}')
            self.logger.debug(f"{player.name} hand score: {score}")

        # 3. Find the best score (lower is better in Cactus Kev's system)
        best_score = min(showdown_dict.values())
        winners = [p for p, score in showdown_dict.items() if score == best_score]
        

        # 4. Split the pot among winners
        pot_share = self.pot / len(winners)
        pot_distribution = {}
        for winner in winners:
            winner.stack += pot_share
            pot_distribution[winner] = pot_share
            self.logger.debug(f"{winner.name} wins {pot_share}")

        # 5. Log the showdown

        return {
            "winners": winners,
            "pot_distribution": pot_distribution,
            "hand_scores": {p.name: showdown_dict[p] for p in winners}
        }

    def _award_pot_to_last_player(self) -> Dict:
        """Award pot to the last remaining player (no showdown)."""
        active_players = [p for p in self.active_players if not p.has_folded]
        if len(active_players) == 1:
            winner = active_players[0]
            winner.stack += self.pot
            self.logger.debug(f"Pot awarded to {winner.name} (last player)")
            return {"winners": [winner], "pot_distribution": {winner: self.pot}}
        else:
            raise ValueError("No single winner found for pot award")

    def get_hand_summary(self) -> Dict:
        """Get a summary of the hand for analysis."""
        return {
            "hand_id": self.hand_id,
            "players": [p.name for p in self.players],
            "start_stacks": self.start_stacks,
            "end_stacks": {p: p.stack for p in self.players},
            "community_cards": [str(card) for card in self.community_cards],
            "action_log": self.action_log,
            "pot": self.pot
        }

    def format_action_log_for_ui(self) -> List[str]:
        """Format the action log for UI display."""
        ui_log = []
        for entry in self.action_log:
            if entry["player"]:
                ui_log.append(f"{entry['player']} {entry['action'].lower()}")
            else:
                ui_log.append(f"System: {entry['action']}")
        return ui_log

    def _get_game_state(self, player, amount_to_call):
        """Return a dict representing the current game state for the controller."""
        highest_bet = max(p.current_bet for p in self.players_in_position_order)
        valid_actions = self._get_valid_actions(player, amount_to_call, highest_bet)
        
        return {
            "phase": self.phase,
            "pot": self.pot,
            "amount_to_call": amount_to_call,
            "community_cards": self.community_cards,
            "player_stack": player.stack,
            "player_position": player.position,
            "player_hole_cards": player.hole_cards,
            "valid_actions": valid_actions,
            "highest_bet": highest_bet,
            "min_raise": self.min_raise,
            "max_raise": self.max_raise
        }

    def _reset_betting_state(self):
        """At the start of a new hand, resets the minimum raise to the minimum raise"""
        if self.phase == Phase.PREFLOP:
            self.last_raise_increment = self.big_blind
        self.current_round_raises = []

    def _get_valid_actions(self, player, amount_to_call, highest_bet):
        """Return valid actions and amounts for current player."""
        valid_actions = {
            'actions': [],
            'raise_amounts': [],
            'min_raise': None,
            'max_raise': None,
            'amount_to_call': amount_to_call,
            'betting_increments': self.betting_increments
        }
        
        # Always can fold
        valid_actions['actions'].append(Action.FOLD)
        
        # Can call if there's something to call
        if amount_to_call > 0:
            valid_actions['actions'].append(Action.CALL)
        else:
            valid_actions['actions'].append(Action.CHECK)
        
        # -- 7/7 looks good
        
        # Can raise if player has chips and it's a valid raise
        if player.stack > amount_to_call:
            min_raise = self._calculate_min_raise(highest_bet)
            max_raise = self._calculate_max_raise(player, highest_bet)
            
            if min_raise <= max_raise:
                if highest_bet == 0:
                    # No one has bet yet - can BET or RAISE
                    valid_actions['actions'].append(Action.BET)
                    valid_actions['actions'].append(Action.RAISE)
                else:
                    # Someone has bet - can only RAISE
                    valid_actions['actions'].append(Action.RAISE)
                
                valid_actions['min_raise'] = min_raise
                valid_actions['max_raise'] = max_raise
                
                # Generate valid raise amounts (respecting betting increments)
                valid_actions['raise_amounts'] = self._generate_raise_amounts(
                    min_raise, max_raise, player.stack
                )
        
        return valid_actions

    def _calculate_min_raise(self, highest_bet):
        """Calculate minimum raise amount."""
        if self.last_raise_increment == 0:
            # First raise of the round (unopened pot)
            # Use big blind as minimum raise if min_raise is not set
            min_raise_amount = self.min_raise if self.min_raise is not None else self.big_blind
            min_raise = highest_bet + min_raise_amount
        else:
            # Subsequent raises must be at least the size of the last raise
            min_raise = highest_bet + self.last_raise_increment
        return min_raise

    def _calculate_max_raise(self, player, highest_bet):
        """Calculate maximum raise amount."""
        if self.max_raise is None:
            # No limit - player can bet their entire stack
            return player.stack
        else:
            # Pot limit or other limit
            return min(self.max_raise, player.stack)

    def _generate_raise_amounts(self, min_raise, max_raise, player_stack):
        """Generate list of valid raise amounts respecting betting increments."""
        amounts = []
        current = min_raise
        
        # Determine increment step based on betting_increments rule
        if self.betting_increments == 'big_blind':
            step = self.big_blind
        elif self.betting_increments == 'small_blind':
            step = self.small_blind
        else:  # 'none'
            step = 0.01  # Small increment for flexibility
        
        while current <= max_raise and current <= player_stack:
            # Only add amounts that follow the betting increment rule
            if self._validate_betting_increment(current):
                amounts.append(current)
            
            if step > 0:
                current += step
            else:
                # For 'none', just add the minimum raise
                amounts.append(current)
                break
        
        return amounts

    def _validate_betting_increment(self, amount):
        """Validate that the bet amount follows the betting increment rule."""
        if self.betting_increments == 'big_blind':
            return amount % self.big_blind == 0
        elif self.betting_increments == 'small_blind':
            return amount % self.small_blind == 0
        else:  # 'none'
            return True  # No increment rule

    def _validate_action(self, action, amount, valid_actions, player, highest_bet):
        # Good Enough
        """Validate that the action is legal."""
        # Good.
        if action not in valid_actions['actions']:
            self.logger.debug(f"Action {action} not in valid actions: {valid_actions['actions']}")
            return False
        # Good
        if action == Action.RAISE:
            player_current_bet = player.current_bet
            raise_increment = amount - highest_bet
            
            self.logger.info(f"VALIDATION: player={player.name}, current_bet={player_current_bet}, "
                             f"amount={amount}, raise_increment={raise_increment}, "
                             f"last_raise_amount={self.last_raise_increment}")
            
            # Good
            if self.last_raise_increment > 0:
                if raise_increment < self.last_raise_increment:
                    self.logger.info(f"INVALID RAISE (raise increment must be bigger than previous raisee increment.): {raise_increment} < {self.last_raise_increment}")
                    return False
            else:
                min_raise_amount = self.min_raise if self.min_raise is not None else self.big_blind
                if raise_increment < min_raise_amount:
                    self.logger.info(f"INVALID (Raise increment not larger than min raise.): {raise_increment} < {min_raise_amount}")
                    return False
            
            # Check betting increment rule
            if not self._validate_betting_increment(amount):
                self.logger.info(f"INVALID BETTING INCREMENT: {amount} doesn't follow {self.betting_increments} rule")
                return False
        
        return True

    def _handle_invalid_action(self, player, valid_actions):
        """Handle invalid action by throwing an error."""
        self.logger.warning(f"Invalid action from {player.name}, defaulting to fold")
        
        # If we can call, call. Otherwise fold.
        if Action.CALL in valid_actions['actions']:
            return Action.CALL, None
        else:
            return Action.FOLD, None

    def _print_game_state_debug(self, player=None, action=None, amount=None):
        """
        Print a formatted game state summary for debugging.
        """
        self.logger.info(f"Pot: ${self.pot:.2f}")

        # 3. Player Contributions
        contributions = [f"{p.name}: ${p.pot_contrib:.2f}" for p in self.players_in_position_order if p.pot_contrib > 0]
        if contributions:
            self.logger.info(f"Contributions: {', '.join(contributions)}")

        # 4. Minimum Raise Amount (if applicable)
        if hasattr(self, 'last_raise_amount') and self.last_raise_increment > 0:
            self.logger.info(f"Min Raise: ${self.last_raise_increment:.2f}")

        # 5. Player Stack States (show if any stack is low or big difference)
        stacks = [p.stack for p in self.players_in_position_order]
        min_stack = min(stacks)
        max_stack = max(stacks)
        if max_stack - min_stack > 5.0 or min_stack < 10.0:
            stack_strs = [f"{p.name}: ${p.stack:.2f}" for p in self.players_in_position_order]
            self.logger.info(f"Stacks: {', '.join(stack_strs)}")

        # Blank line for readability
        self.logger.info("")
    
    def distribute_pot(self, pot: float, winners: list[Player]):
        chip_unit = self.small_blind
        n = len(winners)
        base_share = math.floor((pot / n) / chip_unit) * chip_unit
        print(base_share)
            