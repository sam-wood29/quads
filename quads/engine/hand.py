import sqlite3
from collections import deque
from collections.abc import Iterator
import quads.engine.player as quads_player
from quads.deuces.card import Card
from quads.deuces.deck import Deck
from quads.deuces.evaluator import Evaluator
from quads.engine.betting_order import BettingOrder
from quads.engine.enums import ActionType, Phase, RaiseSetting
from quads.engine.game_state import GameState, PlayerState
from quads.engine.logger import get_logger
from quads.engine.money import Cents, from_cents, to_cents
from quads.engine.player import Player, Position
from quads.engine.pot_manager import PotManager
from quads.engine.validated_action import ValidatedAction

from .phase_controller import PhaseController


class Hand:
    def __init__ (self, players: list[Player], id: int, deck: Deck, dealer_index: int, game_session_id: int, 
                  conn: sqlite3.Connection, script: dict | None = None, 
                  raise_settings: RaiseSetting = RaiseSetting.STANDARD, small_blind: float = 0.25, 
                  big_blind: float = 0.50):
        self.players = players
        self.id = id
        self.deck = deck
        self.dealer_index = dealer_index
        self.game_session_id = game_session_id
        self.conn = conn
        self.script = script
        self.raise_settings = raise_settings
        self.small_blind = small_blind
        self.big_blind = big_blind
        # Remove script_index - no longer needed
        self.community_cards: list[int] = []
        self.pot = 0.0
        self.step_number = 1
        self.logger = get_logger(__name__)
        
        self.highest_bet: int = 0 # Biggest contributed amount on current street
        self.last_full_raise_increment: int = 0 # Size of last full raise (reopen threshold)
        self.last_aggressor: Position | None = None  # Who made the last full raise
        self.acted_since_last_full_raise: set[Position] = set()  # Who has acted since last full raise
        
        # Initialize pot manager with player IDs
        self.pot_manager = PotManager({p.id for p in self.players})
        
        # Initialize players in button order (will be updated in play() if needed)
        self.players_in_button_order = self._assign_positions()
        
        # MONEY: Convert blinds to cents at hand start
        self.small_blind_cents = to_cents(small_blind)
        self.big_blind_cents = to_cents(big_blind)
        
        # Initialize game state with a default phase first
        self.game_state = self._create_initial_game_state()
        self.phase_controller = PhaseController(self.game_state, self.conn, self)
        
        # Set initial phase
        self.phase = Phase.DEAL
        
    def __str__(self) -> str:
        """Comprehensive string representation for debugging."""
        # Convert cents to dollars for display
        pot_dollars = self.pot
        
        # Format community cards
        if self.community_cards:
            try:
                from quads.deuces.card import Card
                cards = [Card.int_to_str(c) for c in self.community_cards]
                community_cards_str = ",".join(cards)
            except Exception:
                community_cards_str = str(self.community_cards)
        else:
            community_cards_str = "None"
        
        
        
        
        
        return (f"-----Hand----\n"
               f"id: {self.id}\n"
               f"phase: {self.phase}\n"
               f"dealer index {self.dealer_index}\n"
               f"player ids in button order:\n"
               f"{', '.join(str(p.id) for p in self.players_in_button_order)}\n"
               f"community cards: {community_cards_str}\n"
               f"pot: ${pot_dollars:.2f}\n")
        
    
    def _create_initial_game_state(self) -> GameState:
        """Create initial game state without circular dependency."""
        player_states = []
        for p in self.players:
            # Convert integer hole cards to string if needed
            if p.hole_cards and isinstance(p.hole_cards, list):
                from quads.deuces.card import Card
                hole_cards = [Card.int_to_str(c) if isinstance(c, int) else c for c in p.hole_cards]
            else:
                hole_cards = None
            player_states.append(PlayerState(
                id=p.id,
                name=p.name,
                stack=p.stack,
                position=str(p.position) if p.position else None,
                hole_cards=hole_cards,
                has_folded=p.has_folded,
                is_all_in=p.all_in,
                current_bet=p.current_bet,
                round_contrib=p.round_contrib,
                hand_contrib=p.hand_contrib,
                # Initialize cents fields from existing data
                stack_cents=p.stack,
                current_bet_cents=p.current_bet,
                committed_cents=p.hand_contrib
            ))
        
        # Add community card attribute to Hand Class
        community_cards = []
        if self.community_cards:
            community_cards = [Card.int_to_str(c) for c in self.community_cards]
            
        dealer_position = ""
        if self.dealer_index is not None:
            dealer_player = next((p for p in self.players if p.seat_index == self.dealer_index), None)
            if dealer_player:
                dealer_position = str(dealer_player.position)
        
        return GameState(
            hand_id=self.id,
            phase=Phase.DEAL.value,  # Start with DEAL phase
            pot=self.pot,
            community_cards=community_cards,
            players=player_states,
            action_on=None,
            last_action=None,
            min_raise=getattr(self, 'min_raise', 0.0),
            max_raise=getattr(self, 'max_raise', 0.0),
            small_blind=self.small_blind,
            big_blind=self.big_blind,
            dealer_position=dealer_position,
            game_session_id=self.game_session_id,  # Add this missing field
            # Initialize cents fields from existing data
            pot_cents=int(self.pot),
            bet_to_call_cents=0
        )

    @property
    def phase(self):
        """Expose phase from game_state for backward compatibility."""
        return Phase(self.game_state.phase)
    
    @phase.setter
    def phase(self, value):
        """Set phase through game_state."""
        self.game_state.phase = value.value if isinstance(value, Phase) else value

    def _update_game_state_pot(self):
        """Update game state's pot field from pot manager."""
        self.game_state.pot = self.pot_manager.total_table_cents() / 100.0

    def play(self):
        # Use phase controller for all phase transitions
        self.phase_controller.enter_phase(Phase.DEAL)
        
        # Script processing is now handled by structured format
        
        self.players = self._reset_players()
        # Only advance dealer for non-scripted hands
        # scripted hands will need to manually advance the dealer
        if self.script is None:
            self.dealer_index = self._advance_dealer()
        self.players_in_button_order = self._assign_positions()
        self._post_blinds()
        self._deal_hole_cards()
        
        # Phase progression using controller
        self.phase_controller.enter_phase(Phase.PREFLOP)
        self._run_betting_round()
        
        # Check if hand continues
        remaining_players = [p for p in self.players if not p.has_folded]
        if len(remaining_players) > 1:
            self.phase_controller.enter_phase(Phase.FLOP)
            self._apply_community_deal(Phase.FLOP)
            self._run_betting_round()
            
            remaining_players = [p for p in self.players if not p.has_folded]
            if len(remaining_players) > 1:
                self.phase_controller.enter_phase(Phase.TURN)
                self._apply_community_deal(Phase.TURN)
                self._run_betting_round()
            
                remaining_players = [p for p in self.players if not p.has_folded]
                if len(remaining_players) > 1:
                    self.phase_controller.enter_phase(Phase.RIVER)
                    self._apply_community_deal(Phase.RIVER)
                    self._run_betting_round()
        
        print(self.phase_controller)
        print("pre showdown")
        print(f"\n{self.__str__()}\n")
        
        print(self.pot_manager.__str__())
        print(self.phase_controller.__str__())
        
        if self.phase_controller._is_uncontested():
            self.phase_controller._award_uncontested_pot()
        else:
            self.phase_controller.enter_phase(Phase.SHOWDOWN)
            self.phase_controller._award_contested_pot()
        
        return self.players, self.id, self.deck, False, self.script, self.dealer_index
        
    def play_manual(self):
        raise RuntimeError("Manual Play not implemented yet.")
        
    def _reset_players(self):
        for p in self.players:
            # MONEY: Convert all player stacks to cents at hand start
            p.stack = int(round(p.stack * 100)) if isinstance(p.stack, float) else p.stack
            # Reset all betting amounts to 0 (in cents)
            p.current_bet = 0
            p.round_contrib = 0
            p.hand_contrib = 0
            # Reset flags
            p.has_checked_this_round = False
            p.all_in = False
            p.has_folded = False
            p.position = None
            p.hole_cards = None
            p.has_acted = False
        return self.players
    
    def _advance_dealer(self):
        """Moves dealer position left once."""
        players = sorted(
            [p for p in self.players],
            key=lambda p: p.seat_index
        )
        current_seat = self.dealer_index
        seat_indices = [p.seat_index for p in players]
        try:
            current_idx = seat_indices.index(current_seat)
        except ValueError:
            current_idx = -1
        next_idx = (current_idx + 1) % len(seat_indices)
        dealer_index = seat_indices[next_idx]
        return dealer_index
    
    def _assign_positions(self) -> list:
        """Returns players in order starting with the button"""
        players=sorted(
            [p for p in self.players],
            key=lambda p: p.seat_index
        )
        num_players = len(players)
        if 2 > num_players or num_players > 10:
            raise ValueError(f"{num_players} players not supported.")
        position_names = quads_player.POSITIONS_BY_PLAYER_COUNT[num_players]
        seat_indices = [p.seat_index for p in players]
        dealer_seat = self.dealer_index
        try:
            dealer_pos_in_list = seat_indices.index(dealer_seat)
        except ValueError:
            raise ValueError("Dealer index not found amoung active players")
        rotated_players = deque(players)
        rotated_players.rotate(-dealer_pos_in_list)
        players_in_order = []
        for pos, player in zip(position_names, rotated_players):
            player.position = pos
            players_in_order.append(player)
        return players_in_order
    
    def _post_blinds(self):
        # MONEY: All blind calculations use cents
        # 1. Get how much small / big blind players are going to pay
        sb_amount = self.small_blind_cents
        bb_amount = self.big_blind_cents
        ordered_player_list = self.players_in_button_order
        
        if len(ordered_player_list) == 2:
            bb_player = ordered_player_list[1]
            sb_player = ordered_player_list[0]
        else:
            sb_player = ordered_player_list[1]
            bb_player = ordered_player_list[2]
        
        # This could be adjusted for certainty. Stacks should be defined as one datatype originally.
        # Convert player stacks to cents if they aren't already
        sb_player.stack = int(sb_player.stack * 100) if isinstance(sb_player.stack, float) else sb_player.stack
        bb_player.stack = int(bb_player.stack * 100) if isinstance(bb_player.stack, float) else bb_player.stack
        
        # player is all in if stack is less than blind
        sb_paid = min(sb_amount, sb_player.stack)
        bb_paid = min(bb_amount, bb_player.stack)
        
        # 2. update data structures to reflect posting of blinds
        # blind player
        # hand.pot_manager
        sb_player.stack -= sb_paid
        sb_player.hand_contrib += sb_paid
        sb_player.round_contrib += sb_paid
        sb_player.current_bet += sb_paid
        
        # Take a look at what this does
        self.pot_manager.post(sb_player.id, sb_paid)
        # keeping gamestate.pot as float right now for backward compatability - I think
        self._update_game_state_pot()
        
        bb_player.stack -= bb_paid
        bb_player.hand_contrib += bb_paid
        bb_player.round_contrib += bb_paid
        bb_player.current_bet += bb_paid
        
        self.pot_manager.post(bb_player.id, bb_paid)
        self._update_game_state_pot()
        
        # "Float pot for backward compatabiltiy". Not sure if that is entirely nescessary.
        self.pot += (bb_paid + sb_paid) / 100  # Keep float pot for backward compatibility
        
        # Log actions using cents
        conn = self.conn
        game_session_id = self.game_session_id
        hand_id = self.id
        step_number = self.step_number
        
        # 3. Log the Actions
        
        
        # Log SB
        player = sb_player
        action = ActionType.POST_SMALL_BLIND.value
        amount_cents = sb_paid  # Use cents directly
        phase = Phase.DEAL.value
        position = sb_player.position
        sb_logged = log_action(conn=conn, game_session_id=game_session_id, hand_id=hand_id, step_number=step_number,
               player=player, action=action, amount_cents=amount_cents, phase=phase, position=position)
        self.step_number += 1
        
        # Log BB
        player = bb_player
        action = ActionType.POST_BIG_BLIND.value
        amount_cents = bb_paid  # Use cents directly
        position = bb_player.position
        bb_logged = log_action(conn=conn, game_session_id=game_session_id, hand_id=hand_id, step_number=step_number,
               player=player, action=action, amount_cents=amount_cents, phase=phase, position=position)
        
        if not bb_logged or not sb_logged:
            raise RuntimeError("Error entering blinds posted into db.")
        
    # Add these new methods to handle structured script format
    def _get_structured_script_action(self, player_id: int, phase: str):
        """Get next action for a player from structured script format."""
        if self.script is None:
            raise RuntimeError("No script provided")
        
        phase_actions = self.script.get(phase, {}).get("actions", {})
        player_actions = phase_actions.get(str(player_id), [])
        
        if not player_actions:
            raise RuntimeError(f"No actions for player {player_id} in phase {phase}")
        
        # Get the first action and remove it from the list
        action = player_actions.pop(0)
        return action

    def _deal_hole_cards(self):
        """Deal hole cards using structured script format."""
        if self.script is None:
            raise RuntimeError("Non scripted dealing not implemented yet. Implement here.")
        
        # Scipted dealing here
        # hole cards here are implemented as list of lists I think -?
        hole_cards = self.script.get("hole_cards", [])
        if not hole_cards:
            raise RuntimeError("No hole cards in script")
        
        # Deal cards to each player in button order
        # Not entirely sure how this works at a glance -? 
        # 1. Assign hole cards
        for i, player in enumerate(self.players_in_button_order):
            # i starts at 0 makes sense to be exclusive
            if i < len(hole_cards):
                cards = hole_cards[i]
                if len(cards) != 2:
                    raise RuntimeError(f"Expected 2 hole cards, got {len(cards)}")
                
                # Convert card strings to Deuces ints - singular datatype
                card_ints = Card.hand_to_binary(cards)
                player.hole_cards = card_ints
                
                # Log the deal
                # 2. Log into the DB
                log_action(
                    self.conn, self.game_session_id, self.id, 
                    self.game_state.next_step_number(),
                    player=player,
                    action=ActionType.DEAL_HOLE.value,
                    phase=self.phase.value,
                    hole_cards=",".join(cards)
                )

    def _rebuild_players_yet_to_act_after_raise(self, action_order: list[Player], raiser: Player) -> list[Player]:
        highest_bet = self.highest_bet
        remaining = [
            p for p in action_order
            if (not p.has_folded) and (p.stack > 0) and (p is not raiser) and (p.current_bet < highest_bet)
        ]
        raiser_index = action_order.index(raiser)
        ordered = []
        for i in range(len(action_order) - 1):
            idx = (raiser_index + 1 + i) % len(action_order)
            candidate = action_order[idx]
            if candidate in remaining:
                ordered.append(candidate)
        return ordered
    
    def get_discrete_raise_amounts(self, player: Player, min_raise: int, max_raise: int) -> list[int]:
        """
        Generate discrete raise buckets: [min_raise_to, 2.5x_open, 3x_open, pot, all_in]
        
        Args:
            player: Player making the raise
            min_raise: Minimum legal raise amount
            max_raise: Maximum raise amount (player's stack)
            
        Returns:
            List of valid raise amounts in cents
        """
        buckets = []
        
        # 1. Min raise (always included if legal)
        if min_raise <= max_raise:
            buckets.append(min_raise)
        
        # 2. Calculate pot size for pot-sized raises
        pot_size = self.pot_manager.total_table_cents()
        
        # 3. Generate discrete buckets
        discrete_amounts = [
            min_raise,  # Already added above
            self._calculate_2_5x_open(min_raise),
            self._calculate_3x_open(min_raise), 
            pot_size,
            player.stack  # All-in
        ]
        
        # 4. Filter by legality and stack constraints
        for amount in discrete_amounts:
            if (amount >= min_raise and 
                amount <= max_raise and 
                amount not in buckets):
                buckets.append(amount)
        
        # Sort buckets for consistent ordering
        buckets.sort()
        
        return buckets
    
    def get_non_discrete_raise_amounts(self, player: Player, min_raise: int, max_raise: int) -> list[int]:
        """
        Generate non-discrete raise amounts using small blind increments.
        Better for manual players who want fine-grained control.
        
        Args:
            player: Player making the raise
            min_raise: Minimum legal raise amount
            max_raise: Maximum raise amount (player's stack)
            
        Returns:
            List of valid raise amounts in cents
        """
        amounts = []
        current = min_raise
        step = self.small_blind_cents  # Use cents
        
        # max_to should be current_bet + stack (total amount player can raise to)
        max_to = player.current_bet + player.stack
        
        while current <= max_to and current <= max_raise:
            amounts.append(current)
            current += step
        
        return amounts
    
    def _generate_raise_amounts(self, player: Player, min_raise: int, max_raise: int) -> list[int]:
        """
        Default raise amount generation - uses discrete buckets.
        For backward compatibility, delegates to get_discrete_raise_amounts.
        """
        return self.get_discrete_raise_amounts(player, min_raise, max_raise)
    
    def _calculate_2_5x_open(self, min_raise: int) -> int:
        """Calculate 2.5x the opening bet size."""
        if self.highest_bet == 0:
            # No bet yet, use big blind as reference
            return int(self.big_blind_cents * 2.5)
        else:
            # There's a bet, use min_raise as reference
            return int(min_raise * 2.5)
    
    def _calculate_3x_open(self, min_raise: int) -> int:
        """Calculate 3x the opening bet size."""
        if self.highest_bet == 0:
            # No bet yet, use big blind as reference
            return int(self.big_blind_cents * 3.0)
        else:
            # There's a bet, use min_raise as reference
            return int(min_raise * 3.0)
    
    def _get_valid_actions(self, player: Player, amount_to_call: int) -> dict:
        """
        Get valid actions for a player.
        
        Returns: Dict: valid actions
        """
        if self.raise_settings != RaiseSetting.STANDARD:
            raise RuntimeError("Raise settings not implemented.")
        
        va = {
            'actions': [],
            'raise_amounts': [],
        }
        
        va["actions"].append(ActionType.FOLD)
        
        if amount_to_call > 0:
            va["actions"].append(ActionType.CALL)
        else:
            va["actions"].append(ActionType.CHECK)
        
        if player.stack > amount_to_call:
            min_raise = self.min_raise_to()
            max_raise = player.stack
            
            if min_raise <= max_raise:
                va["actions"].append(ActionType.RAISE)
                va["raise_amounts"] = self._generate_raise_amounts(player, min_raise, max_raise)
        
        return va
            
        
    def _select_validate_action(self, ap: Player, valid_actions: dict):
        """
        Select and validate action from structured script format.
        
        Returns: 
        """
        # TODO: add switch for agentic / manual inputs here
        if self.script is None:
            raise RuntimeError("No script provided")
        
        # Simplified debug output
        # This may be good to look at for debugging output
        current_phase = self.phase.value
        phase_actions = self.script.get(current_phase, {}).get("actions", {})
        player_actions = phase_actions.get(ap.seat_index, [])
        
        print(f"DEBUG: P{ap.seat_index} ({ap.position}) in {current_phase}: {player_actions}")
        
        if not player_actions:
            raise RuntimeError(f"No actions for player {ap.seat_index} in phase {current_phase}")
        
        # Get the first action and remove it from the list
        action = player_actions.pop(0)
        
        # Convert action to ValidatedAction
        action_type = ActionType(action["type"])
        amount = action.get("amount", 0)
        
        # Convert amount to cents if it's a float
        if isinstance(amount, float):
            amount = to_cents(amount)
        
        # Validate the action
        return self.validate_action(ap, action_type, amount)
    
    def _get_player_action(self, acting_player: Player, game_state: GameState):
        """Get player action from script or manual input."""
        ap = acting_player
        amount_to_call = self.highest_bet - ap.current_bet
        valid_actions = self._get_valid_actions(player=ap, amount_to_call=amount_to_call)
        validated_action = self._select_validate_action(ap=ap, valid_actions=valid_actions)
        # NOTE: Validated action type not nesscessarily used fully...
        selected_action = validated_action.action_type
        selected_amount = validated_action.amount
        return selected_action, selected_amount, amount_to_call
    
    def handle_player_action(self, game_state: GameState, selected_action: ActionType, selected_amount: int,
                         acting_player: Player, amount_to_call: int, highest_bet: int):
        """Handle a player action."""
        
        # Redundant, but whatever
        # selected_amount is already in cents, just ensure it's an int
        amount_cents = int(selected_amount) if selected_amount else 0
        
        # Validate the action
        try:
            validated = self.validate_action(acting_player, selected_action, amount_cents)
        except ValueError as e:
            # Log validation failure
            self.logger.error(f"Action validation failed: {e}")
            raise
        
        # Log before state
        self._log_betting_state_before(acting_player, validated)
        
        # Apply the action
        if validated.action_type == ActionType.FOLD:
            self.apply_fold(acting_player, validated)
        elif validated.action_type == ActionType.CHECK:
            self.apply_check(acting_player, validated)
        elif validated.action_type == ActionType.CALL:
            self.apply_call(acting_player, validated)
        elif validated.action_type == ActionType.RAISE:
            if self.highest_bet == 0:
                self.apply_bet(acting_player, validated)
            else:
                self.apply_raise(acting_player, validated)
        
        # Log after state
        self._log_betting_state_after(acting_player, validated)
        
        return selected_action

    def _log_betting_state_before(self, player: Player, validated: ValidatedAction):
        """Log betting state before action."""
        # TODO: NOTE: This use of logging is a cluster
        self.logger.debug(
            f"Before action: {player.position} {validated.action_type.value} "
            f"highest_bet={self.highest_bet}, "
            f"last_full_raise_increment={self.last_full_raise_increment}, "
            f"last_aggressor={self.last_aggressor}"
        )

    def _log_betting_state_after(self, player: Player, validated: ValidatedAction):
        """Log betting state after action."""
        # NOTE: Again, this method of logging really upests me
        self.logger.debug(
            f"After action: {player.position} {validated.action_type.value} "
            f"highest_bet={self.highest_bet}, "
            f"last_full_raise_increment={self.last_full_raise_increment}, "
            f"last_aggressor={self.last_aggressor}, "
            f"reopen_action={validated.reopen_action}"
        )
        
    
    def _get_score(self, hand_cs: str, ccs: str) -> tuple[int, int]:
        hole_card_strings = [card.strip() for card in hand_cs.split(',')]
        hand_cards = [Card.new(card_str) for card_str in hole_card_strings]
        
        
        board = self.community_cards
        
        evaluator = Evaluator()
        score = evaluator.evaluate(hand_cards, board)
        hand_class = evaluator.get_rank_class(score)
        
        return score, hand_class
    
    def _evaluate_player_hand(self, player: Player) -> tuple[int, str]:
        """Evaluate a player's hand strength for showdown."""
        if not player.hole_cards or len(player.hole_cards) != 2:
            raise ValueError(f"Player {player.id} has invalid hole cards: {player.hole_cards}")
        
        if len(self.community_cards) != 5:
            raise ValueError(f"Invalid community cards length: {len(self.community_cards)}")
        
        evaluator = Evaluator()
        score = evaluator.evaluate(player.hole_cards, self.community_cards)
        hand_class = evaluator.get_rank_class(score)
        hand_class_str = evaluator.class_to_string(hand_class)
        
        return score, hand_class_str
    
    def _rank_players_for_showdown(self) -> dict[int, int]:
        """Rank all remaining players by hand strength (lower score = better hand)."""
        remaining_players = [p for p in self.players if not p.has_folded]
        
        if len(remaining_players) < 2:
            raise ValueError("Need at least 2 players for showdown")
        
        # Evaluate all hands
        player_scores = {}
        for player in remaining_players:
            try:
                score, hand_class = self._evaluate_player_hand(player)
                player_scores[player.id] = score
                self.logger.info(f"Player {player.id} ({player.position}): {hand_class} (score: {score})")
            except Exception as e:
                self.logger.error(f"Failed to evaluate player {player.id}: {e}")
                raise
        
        # Sort by score (lower is better) and assign ranks
        sorted_players = sorted(player_scores.items(), key=lambda x: x[1])
        ranks = {}
        
        current_rank = 1
        for i, (player_id, score) in enumerate(sorted_players):
            if i > 0 and score != sorted_players[i-1][1]:
                # Different score, advance rank
                current_rank = i + 1
            ranks[player_id] = current_rank
        
        return ranks
         
         
    def _get_community_cards(self, phase: Phase) -> str:
        """Get Community cards for logging."""
        if not self.community_cards:
            return ""
        
        card_strings = [Card.int_to_str(card) for card in self.community_cards]
        return ",".join(card_strings)
        
    
    def _deal_community_cards(self) -> str:
        script = self.script if self.script else None
        if script is not None:
            print("scripted game")
            # Get community cards from structured script format
            board = script["board"]
            
            if self.phase == Phase.FLOP:
                card_strings = board[:3]  # First 3 cards for flop
            elif self.phase == Phase.TURN:
                card_strings = [board[3]]  # 4th card for turn
            elif self.phase == Phase.RIVER:
                card_strings = [board[4]]  # 5th card for river
            else:
                raise ValueError(f"Unexpected phase for community deal: {self.phase}")
            
            # convert to deuces ints
            cards = [Card.new(card_str) for card_str in card_strings]
        else:
            print("not scripted game")
            raise ValueError("Unscripted play not implemented yet. :(")
        
        return cards

    def _apply_community_deal(self, phase: Phase) -> None:
        """Deal community cards for the given phase using structured script format."""
        if self.script is None:
            raise RuntimeError("No script provided for community card dealing")
        
        board = self.script.get("board", [])
        if not board:
            raise RuntimeError("No board cards in script")
        
        # Determine which cards to deal based on phase
        if phase == Phase.FLOP:
            cards_to_deal = board[:3]
        elif phase == Phase.TURN:
            cards_to_deal = board[3:4]
        elif phase == Phase.RIVER:
            cards_to_deal = board[4:5]
        else:
            raise RuntimeError(f"Unexpected phase for community deal: {phase}")
        
        if not cards_to_deal:
            raise RuntimeError(f"No cards available for {phase}")
        
        # Convert card strings to Deuces ints and add to community cards
        card_ints = Card.hand_to_binary(cards_to_deal)
        self.community_cards.extend(card_ints)
        
        # Log the deal
        log_action(
            self.conn, self.game_session_id, self.id,
            self.game_state.next_step_number(),
            action=ActionType.DEAL_COMMUNITY.value,
            phase=phase.value,
            community_cards=",".join(cards_to_deal)
        )

    
    def _get_last_player_action_data(self, player: Player) -> dict:
        """
        Get the last action data for a specific player in the current hand.
        Returns a dict with the preflop metrics we want to reuse.
        """
        player_id = player.id
        hand_id = self.id
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT hole_cards, hole_card1, hole_card2, hand_class, pf_hand_class, 
                    high_rank, low_rank, is_pair, is_suited, gap, chen_score
                FROM actions 
                WHERE player_id = ? AND hand_id = ? 
                ORDER BY step_number DESC 
                LIMIT 1
            """, (player_id, hand_id))
            
            result = cursor.fetchone()
            if result:
                return {
                    'hole_cards': result[0],
                    'hole_card1': result[1], 
                    'hole_card2': result[2],
                    'hand_class': result[3],
                    'pf_hand_class': result[4],
                    'high_rank': result[5],
                    'low_rank': result[6],
                    'is_pair': result[7],
                    'is_suited': result[8],
                    'gap': result[9],
                    'chen_score': result[10]
                }
            return {}
        except Exception as e:
            print(f"ERROR - Failed to get last player action data: {e}")
        return {}


    def _run_betting_round(self):
        """Run a complete betting round."""
        # Use phase controller to start betting round
        self.phase_controller.start_betting_round()
        
        # Initialize Hand's betting state for this round
        self._reset_betting_round_state()
        
        # Get the theoretical betting order for this phase
        num_players = len(self.players)
        
        # Pass the button position to get correct betting order
        button_pos = Position.BUTTON
        order = BettingOrder.get_betting_order(num_players, self.phase, button_pos)
        
        # Determine who acts first this round
        first_to_act = order[0]
        
        while True:
            progressed = False
            
            # Iterate through positions that can act
            for pos in self.iter_action_order(order, start_from=first_to_act):
                if pos in self.acted_since_last_full_raise and self.last_aggressor is None:
                    # Everyone has acted since last raise (or from start); round ends
                    # TODO: investigate hand.acted_since_last_full_raise_data_structure
                    break
                
                # Get the player at this position
                acting_player = self._get_player_by_position(pos)
                if not acting_player:
                    continue
                
                # Get player action
                game_state = self.get_game_state(action_on_player_id=acting_player.id)
                selected_action, selected_amount, amount_to_call = self._get_player_action(
                    acting_player=acting_player, game_state=game_state
                )

                # Handle the action
                result = self.handle_player_action(
                    game_state=game_state,
                    selected_action=selected_action,
                    selected_amount=selected_amount,
                    acting_player=acting_player,
                    amount_to_call=amount_to_call,
                    highest_bet=self.highest_bet
                )
                
                progressed = True
                
                # Check if street should close after this action
                if self.phase_controller.maybe_close_street_and_advance():
                    # Street closed, uncalled bets handled by phase controller
                    return
                
                # If this was a full raise, restart iteration after the raiser
                if result == ActionType.RAISE:
                    if self.last_aggressor == pos:  # This was a full raise
                        first_to_act = self._next_in_order(order, pos)
                        break  # Restart loop so action continues after raiser
            
            if not progressed:
                # No one could act; end round
                break
            
            if self.last_aggressor is None:
                # Completed a lap with no raise
                break
        
        # Handle uncalled bets at end of betting round
        # TODO: NOTE: is this even possible, if not, git rid potentially.
        if self.last_aggressor:
            aggressor = self._get_player_by_position(self.last_aggressor)
            if aggressor:
                self._return_uncalled_bet(aggressor)

    def get_game_state(self, action_on_player_id: int = None, last_action: dict = None) -> GameState:
        player_states = []
        for p in self.players:
            # Convert integer hole cards to string if needed
            # TODO: Can be removed I think barring test functionality?
            # p.hole_cards should always be a list of cards
            # Gamestate holds cards as strs
            if p.hole_cards and isinstance(p.hole_cards, list):
                hole_cards = [Card.int_to_str(c) if isinstance(c, int) else c for c in p.hole_cards]
            else:
                hole_cards = None
            player_states.append(PlayerState(
                id=p.id,
                name=p.name,
                stack=p.stack,
                position=str(p.position) if p.position else None,
                hole_cards=hole_cards,
                has_folded=p.has_folded,
                is_all_in=p.all_in,
                current_bet=p.current_bet,
                round_contrib=p.round_contrib,
                hand_contrib=p.hand_contrib
            ))
        # Add community card attribute to Hand Class
        community_cards = []
        if self.community_cards:
            community_cards = [Card.int_to_str(c) for c in self.community_cards]
            
        dealer_position = ""
        if self.dealer_index is not None:
            dealer_player = next((p for p in self.players if p.seat_index == self.dealer_index), None)
            if dealer_player:
                dealer_position = str(dealer_player.position)
        # Game state holds list of player states
        return GameState(
            hand_id=self.id,
            phase=str(self.phase),
            pot=self.pot,
            community_cards=community_cards,
            players=player_states,
            action_on=action_on_player_id,
            last_action=last_action,
            min_raise=getattr(self, 'min_raise', 0.0),
            max_raise=getattr(self, 'max_raise', 0.0),
            small_blind=self.small_blind,
            big_blind=self.big_blind,
            dealer_position=dealer_position
        )
    
    def _position_can_act(self, pos: Position) -> bool:
        """Returns True iff the seat is not folded, not all-in, and still facing action."""
        # Find the player with this position
        player = next((p for p in self.players if p.position == pos), None)
        if not player:
            return False
        
        if player.has_folded:
            return False
        if player.all_in:
            return False
        
        # If there is a bet, seat must have option to act (hasn't called or cannot check)
        return self._seat_still_has_action(player)
    
    def _seat_still_has_action(self, player: Player) -> bool:
        """Check if a player still has action to take."""
        if self.highest_bet == 0:
            return not getattr(player, 'has_checked_this_round', False)
        
        need = self.highest_bet - player.current_bet
        if need > 0:
            return True  # must act
        
        # matched: has action only if there has been NO bet this street (preflop blinds don't count)
        return (self.last_aggressor is None) and (not getattr(player, 'has_checked_this_round', False))

    def iter_action_order(
        self,
        order: list[Position],
        start_from: Position | None = None,
    ) -> Iterator[Position]:
        """
        Yields positions in table-driven 'order', optionally rotated to start
        at 'start_from', filtering seats that cannot act right now.
        
        Args:
            order: The theoretical betting order from BettingOrder
            start_from: Optional position to start iteration from (for action continuation)
            
        Yields:
            Positions where _position_can_act(pos) is True, in order
        """
        if not order:
            return
        
        # Use deque for efficient rotation
        q = deque(order)
        
        if start_from is not None:
            # Add safety check to prevent infinite loop
            if start_from not in order:
                raise ValueError(f"start_from position {start_from} not found in order {order}")
            
            # Rotate until start_from is at the beginning
            while q[0] != start_from:
                q.rotate(-1)
        
        # Track how many positions we've seen to prevent infinite loops
        seen = 0
        total = len(q)
        
        while seen < total:
            pos = q[0]
            q.rotate(-1)
            seen += 1
            
            if self._position_can_act(pos):
                yield pos

    def _next_in_order(self, order: list[Position], pos: Position) -> Position:
        """Get the next position after 'pos' in the betting order."""
        try:
            i = order.index(pos)
            return order[(i + 1) % len(order)]
        except ValueError:
            # If position not found, return first position as fallback
            return order[0] if order else None
        
    def min_raise_to(self) -> int:
        """
        Single source of truth for minimum raise validation.
        
        If no bet yet (highest_bet == 0): first bet must be >= big_blind
        If there is a bet: raise must be >= highest_bet + last_full_raise_increment
        """
        if self.highest_bet == 0:
            return self.big_blind_cents
        return self.highest_bet + self.last_full_raise_increment

    def facing_to_call(self, pos: Position) -> int:
        """How much a position needs to call."""
        player = next((p for p in self.players if p.position == pos), None)
        if not player:
            return 0
        return max(0, self.highest_bet - player.current_bet)

    def can_reopen(self, raise_to: int) -> bool:
        """Determine if a raise amount would reopen action."""
        if self.highest_bet == 0:
            # First bet of the street
            return raise_to >= self.big_blind_cents
        
        raise_increment = raise_to - self.highest_bet
        return raise_increment >= self.last_full_raise_increment

    def _reset_betting_round_state(self):
        """Reset betting round state for new street."""
        self.last_aggressor = None
        # How are we using this variable?
        self.acted_since_last_full_raise.clear()
        self.last_full_raise_increment = self.big_blind_cents # makes sense
        
        if self.phase == Phase.PREFLOP:
            # Preflop: blinds are already posted, so highest_bet should be BB
            self.highest_bet = self.big_blind_cents
        else:
            # Postflop: no blinds, starts fresh
            self.highest_bet = 0
        
        # Reset per-player per-street flags and betting state
        for player in self.players:
            if self.phase != Phase.PREFLOP:
                # if not postflop, should not need to reset here.
                # Postflop: reset current_bet to 0 (no blinds)
                player.current_bet = 0
            # Always reset the checked flag for new streets
            if hasattr(player, 'has_checked_this_round'):
                player.has_checked_this_round = False

    def apply_bet(self, player: Player, validated: ValidatedAction) -> None:
        """Apply a bet (first bet of the street)."""
        # MONEY: All betting calculations use cents
        if self.highest_bet != 0:
            raise ValueError("apply_bet called when there's already a bet")
        
        bet_amount = validated.amount
        additional_bet = bet_amount - player.current_bet
        
        # Update player state
        player.stack -= additional_bet
        player.current_bet += additional_bet
        player.round_contrib += additional_bet
        player.hand_contrib += additional_bet
        
        # Update pot manager
        self.pot_manager.post(player.id, additional_bet)
        self._update_game_state_pot()
        
        # Update float pot for backward compatibility
        self.pot += additional_bet / 100
        
        # Update betting state
        self.highest_bet = bet_amount
        
        # Only update last_full_raise_increment if this is a full bet (>= BB)
        if bet_amount >= self.big_blind_cents:
            self.last_full_raise_increment = bet_amount
        
        # Treat first bet like a full raise for iteration purposes
        self.last_aggressor = player.position
        self.acted_since_last_full_raise.clear()  # Reopen action
        self.acted_since_last_full_raise.add(player.position)  # Mark betting player as acted
        
        # Log the bet action using cents
        log_action(
            conn=self.conn,
            game_session_id=self.game_session_id,
            hand_id=self.id,
            step_number=self.step_number,
            player=player,
            action=ActionType.BET.value,
            amount_cents=bet_amount,
            phase=self.phase.value,
            position=player.position
        )
        self.step_number += 1

    def apply_raise(self, player: Player, validated: ValidatedAction) -> None:
        """Apply a raise."""
        # MONEY: All raise calculations use cents
        if validated.action_type != ActionType.RAISE:
            raise ValueError("apply_raise called with non-raise action")
        
        raise_to = validated.amount
        additional_bet = raise_to - player.current_bet
        
        # Handle all-in scenario
        if additional_bet > player.stack:
            # Cap the raise to what the player can afford
            additional_bet = player.stack
            player.all_in = True
        
        # Update player state
        player.stack -= additional_bet
        player.current_bet += additional_bet
        player.round_contrib += additional_bet
        player.hand_contrib += additional_bet
        
        # Update pot manager
        self.pot_manager.post(player.id, additional_bet)
        self._update_game_state_pot()
        
        # Update float pot for backward compatibility
        self.pot += additional_bet / 100
        
        # Check for all-in
        if player.stack == 0:
            player.all_in = True
        
        # Update betting state
        self.highest_bet = raise_to
        
        if validated.is_full_raise: # TODO: NOTE: again, not entirely sure on this one...
            # Full raise - reopen action
            self.last_full_raise_increment = validated.raise_increment
            self.last_aggressor = player.position
            self.acted_since_last_full_raise.clear()  # Reset acted tracking
        else:
            # Short raise (usually all-in) - don't reopen
            # last_full_raise_increment stays the same
            # last_aggressor stays the same
            pass
        
        # Mark player as acted
        self.acted_since_last_full_raise.add(player.position)
        
        # Log the raise action using cents
        log_action(
            conn=self.conn,
            game_session_id=self.game_session_id,
            hand_id=self.id,
            step_number=self.step_number,
            player=player,
            action=ActionType.RAISE.value,
            amount_cents=raise_to,
            phase=self.phase.value,
            position=player.position
        )
        self.step_number += 1

    def apply_call(self, player: Player, validated: ValidatedAction) -> None:
        """Apply a call."""
        # MONEY: All call calculations use cents
        call_amount = validated.amount
        
        # Update player state
        player.stack -= call_amount
        player.current_bet += call_amount
        player.round_contrib += call_amount
        player.hand_contrib += call_amount
        
        # Update pot manager
        self.pot_manager.post(player.id, call_amount)
        self._update_game_state_pot()
        
        # Update float pot for backward compatibility
        self.pot += call_amount / 100
        
        # Check for all-in
        if player.stack == 0:
            player.all_in = True
        
        # Mark player as acted
        self.acted_since_last_full_raise.add(player.position)
        
        # Log the call action using cents
        log_action(
            conn=self.conn,
            game_session_id=self.game_session_id,
            hand_id=self.id,
            step_number=self.step_number,
            player=player,
            action=ActionType.CALL.value,
            amount_cents=call_amount,
            phase=self.phase.value,
            position=player.position
        )
        self.step_number += 1

    def apply_check(self, player: Player, validated: ValidatedAction) -> None:
        """Apply a check."""
        # Mark player as acted
        self.acted_since_last_full_raise.add(player.position)
        # Mark player as having checked this round
        player.has_checked_this_round = True
        
        # Log the check action
        log_action(
            conn=self.conn,
            game_session_id=self.game_session_id,
            hand_id=self.id,
            step_number=self.step_number,
            player=player,
            action=ActionType.CHECK.value,
            amount_cents=0,
            phase=self.phase.value,
            position=player.position
        )
        self.step_number += 1

    def apply_fold(self, player: Player, validated: ValidatedAction) -> None:
        """Apply a fold."""
        player.has_folded = True
        
        # Mark player as folded in pot manager
        self.pot_manager.mark_folded(player.id)
        
        # Mark player as acted
        self.acted_since_last_full_raise.add(player.position)
        
        # Log the fold action
        log_action(
            conn=self.conn,
            game_session_id=self.game_session_id,
            hand_id=self.id,
            step_number=self.step_number,
            player=player,
            action=ActionType.FOLD.value,
            amount_cents=0,
            phase=self.phase.value,
            position=player.position
        )
        self.step_number += 1

    def _return_uncalled_bet(self, aggressor: Player) -> None:
        """Return uncalled portion of a bet to the aggressor."""
        # MONEY: All uncalled bet calculations use cents
        # TODO: NOTE: Not entirely sure on an instance where this is applicable...I should find out...
        if not aggressor:
            return
        
        # Find other players who haven't folded
        other_players = [p for p in self.players if not p.has_folded and p != aggressor]
        
        if not other_players:
            # Everyone folded - return entire bet minus blinds
            uncalled_amount = aggressor.current_bet - self.big_blind_cents
        else:
            # Some players called - calculate uncalled portion
            uncalled_amount = self.highest_bet - max(p.current_bet for p in other_players)
        
        if uncalled_amount <= 0:
            return  # No uncalled portion
        
        # Return the uncalled amount to the aggressor
        aggressor.stack += uncalled_amount
        aggressor.hand_contrib -= uncalled_amount
        
        # Update pot manager
        self.pot_manager.contributed[aggressor.id] -= uncalled_amount
        
        # Update float pot for backward compatibility
        self.pot -= uncalled_amount / 100
        
        self.logger.info(f"Returned {uncalled_amount} cents uncalled bet to {aggressor.id}")
        
        # Log the uncalled bet return using cents
        log_action(
            conn=self.conn,
            game_session_id=self.game_session_id,
            hand_id=self.id,
            step_number=self.step_number,
            player=aggressor,
            action="return_uncalled_bet",
            amount_cents=uncalled_amount,
            phase=self.phase.value,
            position=aggressor.position,
            detail="Returned uncalled portion of bet"
        )
        self.step_number += 1

    def validate_action(self, player: Player, action: ActionType, amount: int = 0) -> ValidatedAction:
        """
        Validates an Action
        Returns: ValidatedAction: 
        
        """
        # NOTE: I think actions may be getting validated twice?
        current_bet = player.current_bet
        amount_to_call = self.highest_bet - current_bet
        
        if action == ActionType.FOLD:
            return ValidatedAction(
                action_type=ActionType.FOLD,
                amount=0,
                is_full_raise=False,
                raise_increment=0,
                reopen_action=False
            )
        
        # TODO: here may need some sort of loop in logic for manual input
        elif action == ActionType.CHECK:
            if amount_to_call > 0:
                raise ValueError(f"Cannot check when facing {amount_to_call} to call")
            return ValidatedAction(
                action_type=ActionType.CHECK,
                amount=0,
                is_full_raise=False,
                raise_increment=0,
                reopen_action=False
            )
        
        # TODO: Will need to add a similiar loop here
        elif action == ActionType.CALL:
            if amount_to_call <= 0:
                raise ValueError("Cannot call when no bet to call")
            if amount_to_call > player.stack:
                # TODO: NOTE: DO I have to update the the player is all in here, or is this noted later in logic?
                # Player is going all-in - they can call their entire stack
                call_amount = player.stack
            else:
                call_amount = amount_to_call
            
            return ValidatedAction(
                action_type=ActionType.CALL,
                amount=call_amount,
                is_full_raise=False,
                raise_increment=0,
                reopen_action=False
            )
        
        # TODO: Loops for a manual player to re-enter logic here.
        elif action == ActionType.RAISE:
            if amount <= self.highest_bet:
                raise ValueError(f"Raise amount {amount} must be greater than current bet {self.highest_bet}")
            
            min_raise = self.min_raise_to()
            if amount < min_raise:
                raise ValueError(f"Raise amount {amount} must be at least {min_raise}")
            
            # Check if player can afford the raise
            additional_amount = amount - player.current_bet
            if additional_amount > player.stack:
                raise ValueError(f"Cannot raise to {amount} (additional {additional_amount}) with stack {player.stack}")
            
            # TODO: NOTE: reopen_aciton, is_full_raise logic is a bit hazy
            raise_increment = amount - self.highest_bet
            is_full_raise = raise_increment >= self.last_full_raise_increment
            
            return ValidatedAction(
                action_type=ActionType.RAISE,
                amount=amount,
                is_full_raise=is_full_raise,
                raise_increment=raise_increment,
                reopen_action=is_full_raise
            )
        
        else:
            raise ValueError(f"Unknown action type: {action}")

    def _get_player_by_position(self, pos: Position) -> Player | None:
        """Get player by position."""
        return next((p for p in self.players if p.position == pos), None)
    
def log_action(
    conn: sqlite3.Connection,
    game_session_id: int,
    hand_id: int,
    step_number: int,
    player: Player = None,  # Changed from player_id
    action: str = None,
    amount: float = None,  # Keep for backward compatibility
    amount_cents: Cents = None,  # MONEY: New parameter for cents
    phase: str = None,
    hole_cards: str = None,
    community_cards: str = None,
    hand_rank_5: int = None,
    hand_class: str = None,
    pot_odds: float = None,
    percent_stack_to_call: float = None,
    amount_to_call: float = None,
    highest_bet: float = None,
    position: str = None,
    detail: str = None,
    hole_card1: str = None,
    hole_card2: str = None,
    pf_hand_class: str = None,
    high_rank: int = None,
    low_rank: int = None,
    is_pair: int = None,
    is_suited: int = None,
    gap: int = None,
    chen_score: float = None
) -> bool:
    try:
        cur = conn.cursor()
        
        # Handle player_id (can be None for phase advances)
        player_id = player.id if player else None
        
        # Convert cents to float for DB if provided
        if amount_cents is not None:
            amount = from_cents(amount_cents)
        
        cur.execute("""
            INSERT INTO actions (
                game_session_id, hand_id, step_number, player_id, position, phase, action, amount,
                hole_cards, hole_card1, hole_card2, community_cards,
                hand_rank_5, hand_class, pf_hand_class, high_rank, low_rank, is_pair, is_suited, gap, chen_score,
                amount_to_call, percent_stack_to_call, highest_bet, pot_odds, detail
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            game_session_id, hand_id, step_number, player_id, position, phase, action, amount,
            hole_cards, hole_card1, hole_card2, community_cards,
            hand_rank_5, hand_class, pf_hand_class, high_rank, low_rank, is_pair, is_suited, gap, chen_score,
            amount_to_call, percent_stack_to_call, highest_bet, pot_odds, detail
        ))
        conn.commit()
        return True
    except Exception as e:
        print(f"ERROR - Failed to log action: {e}")
        return False
    
def _calculate_pot_odds(amt_to_call: float, c_pot: float) -> float:
    pot_odds = round((amt_to_call / (c_pot + amt_to_call)) * 100, 2)
    return pot_odds

def _calculate_pct_stack_to_call(p_stack: float, amount_to_call: float) -> float:
    return round(((amount_to_call/p_stack)* 100), 2) 