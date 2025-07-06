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
                 hand_id: Optional[str] = None):
        """
        Initialize a new hand.
        
        Args:
            players: List of Player objects participating in this hand
            small_blind: Small blind amount
            big_blind: Big blind amount  
            dealer_index: Seat index of the dealer
            logger: Logger instance for this hand
            hand_id: Unique identifier for this hand
        """
        self.players = players
        self.small_blind = small_blind
        self.big_blind = big_blind
        self.dealer_index = dealer_index
        self.logger = logger or setup_logger(f"hand_{hand_id}" if hand_id else "hand")
        self.logger.setLevel(logging.INFO)
        self.hand_id = hand_id
        
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
        
        
        self.logger.debug(f"Hand initialized with {len(players)} players, dealer at seat {dealer_index}")
        self.logger.debug(f"Starting stacks: {self.start_stacks}")
        
        

    def play(self) -> Dict:
        """
        Play a complete hand from start to finish.
        
        Returns:
            Dict containing hand results (winners, pot distribution, etc.)
        """
        self.logger.debug("Starting hand play")
        
        try:
            # Reset players for new hand
            self._reset_players()
            
            # Assign positions and post blinds
            self._assign_positions()
            self._post_blinds()
            
            # Deal hole cards
            self._deal_hole_cards()
            
            # Debugging Statement:
            for player in self.players:
                self.logger.info(f'player: {player.name} : {player.position}')
            
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
        self.logger.debug("Resetting players for new hand")
        for player in self.players:
            player.reset_for_new_hand()
        self.active_players = [p for p in self.players if p.is_playing]

    def _assign_positions(self):
        """Assign positions to players based on dealer index."""
        self.logger.info("Assigned Player Positions")
        
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
            self.logger.info(f"Player {player.name}    {player.position}")
        
        # for use of blinds, betting, etc.        
        self.players_in_position_order = players_in_position_order
        self.positions_assigned = True

    def _post_blinds(self, sb_amount=None, bb_amount=None):
        """Post small and big blinds."""
        self.logger.debug("Posting blinds")
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

        self.logger.debug(f"{sb_player.name} posts SB: {sb_paid}, {bb_player.name} posts BB: {bb_paid}, pot: {self.pot}")
        self.blinds_posted = True

    def _deal_hole_cards(self):
        """Deal two hole cards to each active player."""
        self.logger.debug("Dealing hole cards")
        for player in self.active_players:
            player.hole_cards = tuple(self.deck.draw(2))
            self._log_action(player, "DEALT_HOLE_CARDS", amount=None, 
                           details=f"Cards: {player.hole_cards}")

    def _deal_flop(self):
        """Deal the flop (three community cards)."""
        self.logger.debug("Dealing flop")
        self.deck.draw(1)  # Burn card
        self.community_cards = self.deck.draw(3)
        self.phase = Phase.FLOP
        self._log_action(None, "DEALT_FLOP", amount=None, 
                        details=f"Flop: {self.community_cards}")

    def _deal_turn(self):
        """Deal the turn (fourth community card)."""
        self.logger.debug("Dealing turn")
        self.deck.draw(1)  # Burn card
        self.community_cards.append(self.deck.draw(1))
        self.phase = Phase.TURN
        self._log_action(None, "DEALT_TURN", amount=None, 
                        details=f"Turn: {self.community_cards[-1]}")

    def _deal_river(self):
        """Deal the river (fifth community card)."""
        self.logger.debug("Dealing river")
        self.deck.draw(1)
        self.community_cards.append(self.deck.draw(1))
        self.phase = Phase.RIVER
        self._log_action(None, "DEALT_RIVER", amount=None, 
                        details=f"River: {self.community_cards[-1]}")

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
        self.logger.debug(f"Running betting round for phase: {phase.name}")
        self.phase = phase

        # Determine action order
        if phase == Phase.PREFLOP:
            action_order = self._get_preflop_action_order()
            self.logger.info('Using preflop action order...')
            for p in action_order:
                self.logger.info(f'{p.name} : {p.position}')
        else:
            action_order = self._get_postflop_action_order()
            self.logger.info('Using postflop action order:')
            for p in action_order:
                self.logger.info(f'{p.name} : {p.position}')

        for player in action_order:
            player.has_acted = False  # Track if player has acted this round

        highest_bet = max(p.current_bet for p in action_order)
        players_yet_to_act = [p for p in action_order if not p.has_folded and p.stack > 0]

        while players_yet_to_act:
            player = players_yet_to_act.pop(0)
            self.logger.info(f'{player.name} is acting player....')
            if player.has_folded or player.stack == 0:
                continue

            # Calculate amount to call
            amount_to_call = highest_bet - player.current_bet

            # Ask controller for action
            action, amount = player.controller.decide(player, self._get_game_state(player, amount_to_call))

            # Apply action
            if action == Action.FOLD:
                player.has_folded = True
                self._log_action(player, "FOLD", amount=None)
                self.logger.debug(f"{player.name} folds.")
            elif action == Action.CALL or (action == Action.CHECK and amount_to_call == 0):
                call_amt = min(amount_to_call, player.stack)
                player.stack -= call_amt
                player.current_bet += call_amt
                self.pot += call_amt
                self._log_action(player, "CALL" if action == Action.CALL else "CHECK", amount=call_amt)
                self.logger.debug(f"{player.name} {'calls' if action == Action.CALL else 'checks'} {call_amt}.")
                self.logger.info(f"Pot after {player.name if player else 'system'} {action}: {self.pot}")
            elif action == Action.RAISE:
                # For simplicity, treat amount as the total bet (not just the raise increment)
                total_bet = amount
                bet_amt = min(total_bet, player.stack)
                player.stack -= bet_amt
                player.current_bet += bet_amt
                self.pot += bet_amt
                highest_bet = player.current_bet
                self._log_action(player, "RAISE", amount=bet_amt)
                self.logger.debug(f"{player.name} raises to {player.current_bet}.")
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

            # End round if only one player remains
            active_players = [p for p in self.players_in_position_order if not p.has_folded and p.stack > 0]
            if len(active_players) == 1:
                self.logger.debug("Only one player remains ({active_players[0].name} wins!), ending betting round.")
                break

        # Reset current_bet for all players for the next round
        for player in self.players_in_position_order:
            player.current_bet = 0

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
        self.logger.debug("Starting showdown")
        self.phase = Phase.SHOWDOWN

        # 1. Get all players who haven't folded
        eligible_players = [p for p in self.players_in_position_order if not p.has_folded]

        # 2. Evaluate each player's hand
        evaluator = Evaluator()
        hand_scores = {}
        for player in eligible_players:
            # Combine hole cards and community cards
            player_hand = list(player.hole_cards) + list(self.community_cards)
            # Convert to integer representation if needed
            # (Assume player_hand is already in the right format for Evaluator)
            score = evaluator.evaluate(list(player.hole_cards), list(self.community_cards))
            hand_scores[player] = score
            self.logger.debug(f"{player.name} hand score: {score}")

        # 3. Find the best score (lower is better in Cactus Kev's system)
        best_score = min(hand_scores.values())
        winners = [p for p, score in hand_scores.items() if score == best_score]

        # 4. Split the pot among winners
        pot_share = self.pot / len(winners)
        pot_distribution = {}
        for winner in winners:
            winner.stack += pot_share
            pot_distribution[winner] = pot_share
            self.logger.debug(f"{winner.name} wins {pot_share}")

        # 5. Log the showdown
        self._log_action(None, "SHOWDOWN", amount=self.pot, details=f"Winners: {[w.name for w in winners]}")

        return {
            "winners": winners,
            "pot_distribution": pot_distribution,
            "hand_scores": {p.name: hand_scores[p] for p in winners}
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

    def _log_action(self, player: Optional[Player], action: str, 
                   amount: Optional[float], details: Optional[str] = None):
        """
        Log an action in structured format for ML/analysis.
        
        Args:
            player: Player who took the action (None for system actions)
            action: Type of action
            amount: Amount involved in the action
            details: Additional details about the action
        """
        log_entry = {
            "player": player.name if player else None,
            "action": action,
            "amount": amount,
            "phase": self.phase.name,
            "pot": self.pot,
            "community_cards": [str(card) for card in self.community_cards],
            "details": details
        }
        
        if player:
            log_entry.update({
                "player_stack": player.stack,
                "player_position": player.position
            })
        
        self.action_log.append(log_entry)
        self.logger.debug(f"Action logged: {log_entry}")
        self.logger.info(f"Pot after {player.name if player else 'system'} {action}: {self.pot}")

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
        return {
            "phase": self.phase,
            "pot": self.pot,
            "amount_to_call": amount_to_call,
            "community_cards": self.community_cards,
            "player_stack": player.stack,
            "player_position": player.position,
            "player_hole_cards": player.hole_cards,
        }