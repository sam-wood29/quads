"""
Rules Engine - Pure game logic without side effects.

This module contains all the poker game rules as pure functions.
No database access, no logging, no side effects - just game logic.
"""

from typing import Any

from .action_data import ActionDecision, AppliedAction, GameStateSnapshot, ValidActions
from .enums import ActionType, Phase
from .money import Cents, to_cents


class RulesEngine:
    """
    Pure poker game rules engine.
    
    All methods are pure functions - same input always produces same output.
    No side effects, no database access, no logging.
    """
    
    def __init__(self, small_blind: float = 0.25, big_blind: float = 0.50):
        self.small_blind_cents = to_cents(small_blind)
        self.big_blind_cents = to_cents(big_blind)
    
    def get_valid_actions(self, state: GameStateSnapshot, player_id: int) -> ValidActions:
        """
        Get valid actions for a player given current game state.
        
        Args:
            state: Current game state snapshot
            player_id: ID of the player to get actions for
            
        Returns:
            ValidActions object with available actions
        """
        player = self._get_player(state, player_id)
        if not player:
            raise ValueError(f"Player {player_id} not found in state")
        
        if player['has_folded']:
            return ValidActions(player_id, [], [], 0, False, False, False)
        
        if player['is_all_in']:
            return ValidActions(player_id, [], [], 0, False, False, False)
        
        amount_to_call = max(0, state.highest_bet - player['current_bet'])
        can_check = amount_to_call == 0
        can_bet = state.highest_bet == 0 and player['stack'] > 0
        can_raise = player['stack'] > amount_to_call
        
        actions = [ActionType.FOLD]
        
        if can_check:
            actions.append(ActionType.CHECK)
        else:
            actions.append(ActionType.CALL)
        
        if can_bet:
            actions.append(ActionType.BET)
        
        if can_raise:
            actions.append(ActionType.RAISE)
        
        # Generate raise amounts
        raise_amounts = []
        if can_raise:
            min_raise = self._get_min_raise_amount(state)
            max_raise = player['stack']
            raise_amounts = self._generate_raise_amounts(min_raise, max_raise, state, player_id)
        
        return ValidActions(
            player_id=player_id,
            actions=actions,
            raise_amounts=raise_amounts,
            amount_to_call=amount_to_call,
            can_check=can_check,
            can_bet=can_bet,
            can_raise=can_raise
        )
    
    def apply_action(self, state: GameStateSnapshot, decision: ActionDecision) -> tuple[GameStateSnapshot, AppliedAction]:
        """
        Apply an action to the game state and return new state + applied action.
        
        Args:
            state: Current game state
            decision: Player's action decision
            
        Returns:
            Tuple of (new_state, applied_action)
        """
        # Validate the action
        self._validate_action(state, decision)
        
        # Create state before snapshot
        state_before = self._create_state_dict(state)
        
        # Apply the action
        new_state = self._apply_action_to_state(state, decision)
        
        # Create state after snapshot
        state_after = self._create_state_dict(new_state)
        
        # Create applied action
        applied_action = AppliedAction(
            player_id=decision.player_id,
            action_type=decision.action_type,
            amount=decision.amount,
            state_before=state_before,
            state_after=state_after,
            metadata={
                'phase': state.phase.value,
                'hand_id': state.hand_id
            }
        )
        
        return new_state, applied_action
    
    def should_advance_phase(self, state: GameStateSnapshot) -> bool:
        """
        Check if the current phase should advance to the next phase.
        
        Args:
            state: Current game state
            
        Returns:
            True if phase should advance
        """
        # Check if only one player remains
        active_players = [p for p in state.players if not p['has_folded']]
        if len(active_players) <= 1:
            return True
        
        # Check if all players have matched the bet
        if state.highest_bet > 0:
            for player in state.players:
                if not player['has_folded'] and not player['is_all_in']:
                    if player['current_bet'] < state.highest_bet:
                        return False
        
        # Check if all players have acted
        return all(state.acted_this_round.values())
    
    def get_next_phase(self, current_phase: Phase) -> Phase:
        """
        Get the next phase in the poker hand sequence.
        
        Args:
            current_phase: Current phase
            
        Returns:
            Next phase
        """
        phase_sequence = {
            Phase.DEAL: Phase.PREFLOP,
            Phase.PREFLOP: Phase.FLOP,
            Phase.FLOP: Phase.TURN,
            Phase.TURN: Phase.RIVER,
            Phase.RIVER: Phase.SHOWDOWN,
            Phase.SHOWDOWN: Phase.SHOWDOWN  # Terminal
        }
        return phase_sequence.get(current_phase, Phase.SHOWDOWN)
    
    def _validate_action(self, state: GameStateSnapshot, decision: ActionDecision) -> None:
        """Validate that an action is legal given the current state."""
        player = self._get_player(state, decision.player_id)
        if not player:
            raise ValueError(f"Player {decision.player_id} not found")
        
        if player['has_folded']:
            raise ValueError("Cannot act after folding")
        
        if player['is_all_in']:
            raise ValueError("Cannot act when all-in")
        
        amount_to_call = max(0, state.highest_bet - player['current_bet'])
        
        if decision.action_type == ActionType.CHECK:
            if amount_to_call > 0:
                raise ValueError(f"Cannot check when facing {amount_to_call} to call")
        
        elif decision.action_type == ActionType.CALL:
            if amount_to_call <= 0:
                raise ValueError("Cannot call when no bet to call")
            if decision.amount > player['stack']:
                raise ValueError(f"Cannot call {decision.amount} with stack {player['stack']}")
        
        elif decision.action_type == ActionType.RAISE:
            if decision.amount <= state.highest_bet:
                raise ValueError(f"Raise amount {decision.amount} must be greater than current bet {state.highest_bet}")
            
            min_raise = self._get_min_raise_amount(state)
            if decision.amount < min_raise:
                raise ValueError(f"Raise amount {decision.amount} must be at least {min_raise}")
            
            additional_amount = decision.amount - player['current_bet']
            if additional_amount > player['stack']:
                raise ValueError(f"Cannot raise to {decision.amount} (additional {additional_amount}) with stack {player['stack']}")
    
    def _apply_action_to_state(self, state: GameStateSnapshot, decision: ActionDecision) -> GameStateSnapshot:
        """Apply an action to the state and return new state."""
        # Create a mutable copy of the state
        new_players = [dict(p) for p in state.players]
        new_acted_this_round = dict(state.acted_this_round)
        new_committed_this_round = dict(state.committed_this_round)
        
        player_idx = self._get_player_index(state, decision.player_id)
        player = new_players[player_idx]
        
        if decision.action_type == ActionType.FOLD:
            player['has_folded'] = True
        
        elif decision.action_type == ActionType.CHECK:
            # No state changes for check
            pass
        
        elif decision.action_type == ActionType.CALL:
            call_amount = min(decision.amount, player['stack'])
            player['stack'] -= call_amount
            player['current_bet'] += call_amount
            player['hand_contrib'] += call_amount
            player['round_contrib'] += call_amount
            
            if player['stack'] == 0:
                player['is_all_in'] = True
        
        elif decision.action_type == ActionType.RAISE:
            additional_amount = decision.amount - player['current_bet']
            additional_amount = min(additional_amount, player['stack'])
            
            player['stack'] -= additional_amount
            player['current_bet'] += additional_amount
            player['hand_contrib'] += additional_amount
            player['round_contrib'] += additional_amount
            
            if player['stack'] == 0:
                player['is_all_in'] = True
        
        # Update round tracking
        new_acted_this_round[decision.player_id] = True
        new_committed_this_round[decision.player_id] = player['round_contrib']
        
        # Update highest bet if this was a raise
        new_highest_bet = state.highest_bet
        new_last_aggressor_seat = state.last_aggressor_seat
        
        if decision.action_type == ActionType.RAISE:
            new_highest_bet = decision.amount
            new_last_aggressor_seat = decision.player_id
        
        # Calculate new pot
        new_pot_cents = sum(p['hand_contrib'] for p in new_players)
        
        return GameStateSnapshot(
            hand_id=state.hand_id,
            phase=state.phase,
            pot_cents=new_pot_cents,
            community_cards=state.community_cards,
            players=new_players,
            highest_bet=new_highest_bet,
            last_raise_increment=state.last_raise_increment,
            last_aggressor_seat=new_last_aggressor_seat,
            street_number=state.street_number,
            acted_this_round=new_acted_this_round,
            committed_this_round=new_committed_this_round
        )
    
    def _get_player(self, state: GameStateSnapshot, player_id: int) -> dict[str, Any]:
        """Get player data from state."""
        for player in state.players:
            if player['id'] == player_id:
                return player
        return None
    
    def _get_player_index(self, state: GameStateSnapshot, player_id: int) -> int:
        """Get player index from state."""
        for i, player in enumerate(state.players):
            if player['id'] == player_id:
                return i
        raise ValueError(f"Player {player_id} not found")
    
    def _get_min_raise_amount(self, state: GameStateSnapshot) -> Cents:
        """Get minimum raise amount."""
        if state.highest_bet == 0:
            return self.big_blind_cents
        return state.highest_bet + state.last_raise_increment
    
    def get_discrete_raise_amounts(self, min_raise: Cents, max_raise: Cents, state: GameStateSnapshot, player_id: int) -> list[Cents]:
        """
        Generate discrete raise buckets: [min_raise_to, 2.5x_open, 3x_open, pot, all_in]
        
        Args:
            min_raise: Minimum legal raise amount
            max_raise: Maximum raise amount (player's stack)
            state: Current game state for pot calculation
            player_id: Player making the raise
            
        Returns:
            List of valid raise amounts in cents
        """
        player = self._get_player(state, player_id)
        if not player:
            return []
        
        buckets = []
        
        # 1. Min raise (always included if legal)
        if min_raise <= max_raise:
            buckets.append(min_raise)
        
        # 2. Calculate pot size for pot-sized raises
        pot_size = self._calculate_pot_size(state)
        
        # 3. Generate discrete buckets
        discrete_amounts = [
            min_raise,  # Already added above
            self._calculate_2_5x_open(state, min_raise),
            self._calculate_3x_open(state, min_raise), 
            pot_size,
            player['stack']  # All-in
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
    
    def get_non_discrete_raise_amounts(self, min_raise: Cents, max_raise: Cents, state: GameStateSnapshot, player_id: int) -> list[Cents]:
        """
        Generate non-discrete raise amounts using small blind increments.
        Better for manual players who want fine-grained control.
        
        Args:
            min_raise: Minimum legal raise amount
            max_raise: Maximum raise amount (player's stack)
            state: Current game state
            player_id: Player making the raise
            
        Returns:
            List of valid raise amounts in cents
        """
        amounts = []
        current = min_raise
        step = self.small_blind_cents
        
        while current <= max_raise:
            amounts.append(current)
            current += step
        
        return amounts
    
    def _generate_raise_amounts(self, min_raise: Cents, max_raise: Cents, state: GameStateSnapshot, player_id: int) -> list[Cents]:
        """
        Default raise amount generation - uses discrete buckets.
        For backward compatibility, delegates to get_discrete_raise_amounts.
        """
        return self.get_discrete_raise_amounts(min_raise, max_raise, state, player_id)
    
    def _calculate_pot_size(self, state: GameStateSnapshot) -> Cents:
        """Calculate current pot size for pot-sized raises."""
        return state.pot_cents
    
    def _calculate_2_5x_open(self, state: GameStateSnapshot, min_raise: Cents) -> Cents:
        """Calculate 2.5x the opening bet size."""
        if state.highest_bet == 0:
            # No bet yet, use big blind as reference
            return int(self.big_blind_cents * 2.5)
        else:
            # There's a bet, use min_raise as reference
            return int(min_raise * 2.5)
    
    def _calculate_3x_open(self, state: GameStateSnapshot, min_raise: Cents) -> Cents:
        """Calculate 3x the opening bet size."""
        if state.highest_bet == 0:
            # No bet yet, use big blind as reference
            return int(self.big_blind_cents * 3.0)
        else:
            # There's a bet, use min_raise as reference
            return int(min_raise * 3.0)
    
    def _create_state_dict(self, state: GameStateSnapshot) -> dict[str, Any]:
        """Create a dictionary representation of state for AppliedAction."""
        return {
            'hand_id': state.hand_id,
            'phase': state.phase.value,
            'pot_cents': state.pot_cents,
            'highest_bet': state.highest_bet,
            'last_aggressor_seat': state.last_aggressor_seat,
            'players': [dict(p) for p in state.players]
        }
