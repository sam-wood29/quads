"""
Unit tests for RulesEngine - Pure game logic without database.

These tests demonstrate that the rules engine works without any side effects.
"""

import pytest

from quads.engine.action_data import ActionDecision, GameStateSnapshot
from quads.engine.enums import ActionType, Phase
from quads.engine.money import to_cents
from quads.engine.rules_engine import RulesEngine


class TestRulesEngine:
    """Test the pure rules engine without database dependencies."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.rules_engine = RulesEngine(small_blind=0.25, big_blind=0.50)
        
        # Create a simple game state for testing
        self.test_state = GameStateSnapshot(
            hand_id=1,
            phase=Phase.PREFLOP,
            pot_cents=to_cents(0.75),  # SB + BB
            community_cards=[],
            players=[
                {
                    'id': 0,
                    'name': 'Player 0',
                    'stack': to_cents(100.0),
                    'current_bet': to_cents(0.25),  # SB
                    'hand_contrib': to_cents(0.25),
                    'round_contrib': to_cents(0.25),
                    'has_folded': False,
                    'is_all_in': False,
                    'position': 'sb'
                },
                {
                    'id': 1,
                    'name': 'Player 1', 
                    'stack': to_cents(100.0),
                    'current_bet': to_cents(0.50),  # BB
                    'hand_contrib': to_cents(0.50),
                    'round_contrib': to_cents(0.50),
                    'has_folded': False,
                    'is_all_in': False,
                    'position': 'bb'
                }
            ],
            highest_bet=to_cents(0.50),
            last_raise_increment=to_cents(0.50),
            last_aggressor_seat=1,  # BB
            street_number=1,
            acted_this_round={0: False, 1: False},
            committed_this_round={0: to_cents(0.25), 1: to_cents(0.50)}
        )
    
    def test_get_valid_actions_sb_facing_bb(self):
        """Test getting valid actions for SB facing BB."""
        valid_actions = self.rules_engine.get_valid_actions(self.test_state, 0)
        
        assert valid_actions.player_id == 0
        assert ActionType.FOLD in valid_actions.actions
        assert ActionType.CALL in valid_actions.actions
        assert ActionType.RAISE in valid_actions.actions
        assert ActionType.CHECK not in valid_actions.actions  # Can't check facing bet
        assert valid_actions.amount_to_call == to_cents(0.25)
        assert valid_actions.can_raise is True
        assert valid_actions.can_bet is False  # There's already a bet
    
    def test_get_valid_actions_bb_no_bet(self):
        """Test getting valid actions for BB when no bet to call."""
        # Create state where BB can check
        state_no_bet = GameStateSnapshot(
            hand_id=1,
            phase=Phase.PREFLOP,
            pot_cents=to_cents(0.75),
            community_cards=[],
            players=[
                {
                    'id': 0,
                    'name': 'Player 0',
                    'stack': to_cents(100.0),
                    'current_bet': to_cents(0.25),
                    'hand_contrib': to_cents(0.25),
                    'round_contrib': to_cents(0.25),
                    'has_folded': False,
                    'is_all_in': False,
                    'position': 'sb'
                },
                {
                    'id': 1,
                    'name': 'Player 1',
                    'stack': to_cents(100.0),
                    'current_bet': to_cents(0.50),
                    'hand_contrib': to_cents(0.50),
                    'round_contrib': to_cents(0.50),
                    'has_folded': False,
                    'is_all_in': False,
                    'position': 'bb'
                }
            ],
            highest_bet=to_cents(0.50),
            last_raise_increment=to_cents(0.50),
            last_aggressor_seat=None,  # No raise yet
            street_number=1,
            acted_this_round={0: True, 1: False},  # SB already acted
            committed_this_round={0: to_cents(0.25), 1: to_cents(0.50)}
        )
        
        valid_actions = self.rules_engine.get_valid_actions(state_no_bet, 1)
        
        assert valid_actions.player_id == 1
        assert ActionType.CHECK in valid_actions.actions
        assert ActionType.CALL not in valid_actions.actions  # No bet to call
        assert valid_actions.amount_to_call == 0
        assert valid_actions.can_check is True
    
    def test_apply_call_action(self):
        """Test applying a call action."""
        decision = ActionDecision(
            player_id=0,
            action_type=ActionType.CALL,
            amount=to_cents(0.25)
        )
        
        new_state, applied_action = self.rules_engine.apply_action(self.test_state, decision)
        
        # Check the applied action
        assert applied_action.player_id == 0
        assert applied_action.action_type == ActionType.CALL
        assert applied_action.amount == to_cents(0.25)
        
        # Check the new state
        player_0 = next(p for p in new_state.players if p['id'] == 0)
        assert player_0['current_bet'] == to_cents(0.50)  # 0.25 + 0.25
        assert player_0['stack'] == to_cents(99.75)  # 100 - 0.25
        assert player_0['hand_contrib'] == to_cents(0.50)  # 0.25 + 0.25
        
        # Check round tracking
        assert new_state.acted_this_round[0] is True
    
    def test_apply_raise_action(self):
        """Test applying a raise action."""
        decision = ActionDecision(
            player_id=0,
            action_type=ActionType.RAISE,
            amount=to_cents(2.00)  # Raise to $2.00
        )
        
        new_state, applied_action = self.rules_engine.apply_action(self.test_state, decision)
        
        # Check the applied action
        assert applied_action.player_id == 0
        assert applied_action.action_type == ActionType.RAISE
        assert applied_action.amount == to_cents(2.00)
        
        # Check the new state
        player_0 = next(p for p in new_state.players if p['id'] == 0)
        assert player_0['current_bet'] == to_cents(2.00)
        assert player_0['stack'] == to_cents(98.25)  # 100 - 1.75 (additional bet)
        assert player_0['hand_contrib'] == to_cents(2.00)
        
        # Check betting state
        assert new_state.highest_bet == to_cents(2.00)
        assert new_state.last_aggressor_seat == 0
    
    def test_apply_fold_action(self):
        """Test applying a fold action."""
        decision = ActionDecision(
            player_id=0,
            action_type=ActionType.FOLD,
            amount=0
        )
        
        new_state, applied_action = self.rules_engine.apply_action(self.test_state, decision)
        
        # Check the applied action
        assert applied_action.player_id == 0
        assert applied_action.action_type == ActionType.FOLD
        assert applied_action.amount == 0
        
        # Check the new state
        player_0 = next(p for p in new_state.players if p['id'] == 0)
        assert player_0['has_folded'] is True
        
        # Player's stack and bets should be unchanged
        assert player_0['stack'] == to_cents(100.0)
        assert player_0['current_bet'] == to_cents(0.25)
    
    def test_validate_invalid_actions(self):
        """Test validation of invalid actions."""
        # Test calling when no bet to call
        invalid_decision = ActionDecision(
            player_id=1,
            action_type=ActionType.CALL,
            amount=to_cents(0.50)
        )
        
        # Create state where BB can check (no bet to call)
        state_no_bet = GameStateSnapshot(
            hand_id=1,
            phase=Phase.PREFLOP,
            pot_cents=to_cents(0.75),
            community_cards=[],
            players=[
                {
                    'id': 0,
                    'name': 'Player 0',
                    'stack': to_cents(100.0),
                    'current_bet': to_cents(0.25),
                    'hand_contrib': to_cents(0.25),
                    'round_contrib': to_cents(0.25),
                    'has_folded': False,
                    'is_all_in': False,
                    'position': 'sb'
                },
                {
                    'id': 1,
                    'name': 'Player 1',
                    'stack': to_cents(100.0),
                    'current_bet': to_cents(0.50),
                    'hand_contrib': to_cents(0.50),
                    'round_contrib': to_cents(0.50),
                    'has_folded': False,
                    'is_all_in': False,
                    'position': 'bb'
                }
            ],
            highest_bet=to_cents(0.50),
            last_raise_increment=to_cents(0.50),
            last_aggressor_seat=None,
            street_number=1,
            acted_this_round={0: True, 1: False},
            committed_this_round={0: to_cents(0.25), 1: to_cents(0.50)}
        )
        
        with pytest.raises(ValueError, match="Cannot call when no bet to call"):
            self.rules_engine.apply_action(state_no_bet, invalid_decision)
    
    def test_should_advance_phase(self):
        """Test phase advancement logic."""
        # Test when all players have acted
        state_all_acted = GameStateSnapshot(
            hand_id=1,
            phase=Phase.PREFLOP,
            pot_cents=to_cents(1.00),
            community_cards=[],
            players=[
                {
                    'id': 0,
                    'name': 'Player 0',
                    'stack': to_cents(99.0),
                    'current_bet': to_cents(0.50),
                    'hand_contrib': to_cents(0.50),
                    'round_contrib': to_cents(0.50),
                    'has_folded': False,
                    'is_all_in': False,
                    'position': 'sb'
                },
                {
                    'id': 1,
                    'name': 'Player 1',
                    'stack': to_cents(99.0),
                    'current_bet': to_cents(0.50),
                    'hand_contrib': to_cents(0.50),
                    'round_contrib': to_cents(0.50),
                    'has_folded': False,
                    'is_all_in': False,
                    'position': 'bb'
                }
            ],
            highest_bet=to_cents(0.50),
            last_raise_increment=to_cents(0.50),
            last_aggressor_seat=None,
            street_number=1,
            acted_this_round={0: True, 1: True},  # Both acted
            committed_this_round={0: to_cents(0.50), 1: to_cents(0.50)}
        )
        
        assert self.rules_engine.should_advance_phase(state_all_acted) is True
        
        # Test when not all players have acted
        assert self.rules_engine.should_advance_phase(self.test_state) is False
    
    def test_get_next_phase(self):
        """Test phase progression."""
        assert self.rules_engine.get_next_phase(Phase.DEAL) == Phase.PREFLOP
        assert self.rules_engine.get_next_phase(Phase.PREFLOP) == Phase.FLOP
        assert self.rules_engine.get_next_phase(Phase.FLOP) == Phase.TURN
        assert self.rules_engine.get_next_phase(Phase.TURN) == Phase.RIVER
        assert self.rules_engine.get_next_phase(Phase.RIVER) == Phase.SHOWDOWN
        assert self.rules_engine.get_next_phase(Phase.SHOWDOWN) == Phase.SHOWDOWN
