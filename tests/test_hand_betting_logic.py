from unittest.mock import Mock

import pytest

from quads.deuces.deck import Deck
from quads.engine.enums import ActionType, Phase, RaiseSetting
from quads.engine.hand import Hand
from quads.engine.player import Player, Position
from quads.engine.validated_action import ValidatedAction


class TestHandBettingLogic:
    """Test the core betting logic and reopen scenarios."""
    
    @pytest.fixture
    def betting_hand(self):
        """Create a Hand instance focused on betting logic testing."""
        # Create minimal players
        players = []
        for i in range(3):  # 3-handed for simpler testing
            player = Mock(spec=Player)
            player.id = i + 1
            player.name = f"Player{i+1}"
            player.stack = 2000  # $20.00 in cents
            player.seat_index = i
            player.current_bet = 0
            player.round_contrib = 0
            player.hand_contrib = 0
            player.has_folded = False
            player.all_in = False
            player.has_checked_this_round = False
            player.position = None
            player.hole_cards = None
            player.has_acted = False
            players.append(player)
        
        # Mock connection
        conn = Mock()
        conn.cursor.return_value.execute.return_value = None
        conn.commit.return_value = None
        
        deck = Deck()
        hand = Hand(
            players=players,
            id=1,
            deck=deck,
            dealer_index=0,
            game_session_id=1,
            conn=conn,
            script=None,
            raise_settings=RaiseSetting.STANDARD,
            small_blind=0.25,
            big_blind=0.50
        )
        
        # Set up positions
        players[0].position = Position.BUTTON
        players[1].position = Position.SB
        players[2].position = Position.BB
        
        return hand
    
    def test_min_raise_to_single_source_of_truth(self, betting_hand):
        """Test that min_raise_to() is the single source of truth for raise validation."""
        # No bet yet - should be big blind
        betting_hand.highest_bet = 0
        assert betting_hand.min_raise_to() == 50  # big_blind_cents
        
        # With existing bet - should be highest_bet + last_full_raise_increment
        betting_hand.highest_bet = 100
        betting_hand.last_full_raise_increment = 50
        assert betting_hand.min_raise_to() == 150  # 100 + 50
    
    def test_validation_separate_from_application(self, betting_hand):
        """Test that validation and application are cleanly separated."""
        player = betting_hand.players[0]
        player.stack = 1000
        player.current_bet = 0
        
        # Validate first
        validated = betting_hand.validate_action(player, ActionType.RAISE, 100)
        assert validated.action_type == ActionType.RAISE
        assert validated.amount == 100
        assert validated.is_full_raise is True  # 100 >= 50
        assert validated.reopen_action is True
        
        # Then apply (should not change validation result)
        betting_hand.apply_bet(player, validated)
        assert betting_hand.highest_bet == 100
        assert betting_hand.last_aggressor == player.position
    
    def test_full_raise_reopens_action(self, betting_hand):
        """Test that full raises reopen action."""
        player = betting_hand.players[0]
        player.position = Position.BUTTON
        player.stack = 1000
        player.current_bet = 0
        
        # First bet (full raise)
        validated = betting_hand.validate_action(player, ActionType.RAISE, 100)
        betting_hand.apply_bet(player, validated)
        
        # Should reopen action
        assert betting_hand.last_aggressor == Position.BUTTON
        assert betting_hand.acted_since_last_full_raise == {Position.BUTTON}
        assert betting_hand.highest_bet == 100
        assert betting_hand.last_full_raise_increment == 100  # Full bet >= BB
    
    def test_short_all_in_does_not_reopen(self, betting_hand):
        """Test that all-in for less than full raise doesn't reopen action."""
        # Set up existing bet
        betting_hand.highest_bet = 100
        betting_hand.last_full_raise_increment = 50
        
        player = betting_hand.players[1]
        player.position = Position.SB
        player.current_bet = 25  # Already posted SB
        player.stack = 25  # Only enough for small raise
        
        # Try to raise to 150 (additional 125, but only 25 available)
        # This should be a short raise that doesn't reopen
        validated = ValidatedAction(
            action_type=ActionType.RAISE,
            amount=150,
            is_full_raise=False,  # 50 < 50 (last_full_raise_increment)
            raise_increment=50,
            reopen_action=False
        )
        
        betting_hand.apply_raise(player, validated)
        
        # Should NOT reopen action
        assert betting_hand.last_aggressor != Position.SB  # Unchanged
        assert betting_hand.highest_bet == 150
        assert betting_hand.acted_since_last_full_raise == {Position.SB}
    
    def test_street_transitions_reset_state(self, betting_hand):
        """Test that street transitions reset betting state correctly."""
        # Set up some betting state
        betting_hand.highest_bet = 200
        betting_hand.last_aggressor = Position.BB
        betting_hand.acted_since_last_full_raise = {Position.BB, Position.SB}
        
        # Transition to flop
        betting_hand.phase = Phase.FLOP
        betting_hand._reset_betting_round_state()
        
        # Should reset for postflop
        assert betting_hand.highest_bet == 0  # No blinds on postflop
        assert betting_hand.last_aggressor is None
        assert betting_hand.acted_since_last_full_raise == set()
        assert betting_hand.last_full_raise_increment == 50  # Still BB size
        
        # Player betting state should reset
        for player in betting_hand.players:
            assert player.current_bet == 0
            assert player.has_checked_this_round is False
    
    def test_preflop_blinds_preserved(self, betting_hand):
        """Test that preflop blinds are preserved during reset."""
        # Set up preflop state
        betting_hand.phase = Phase.PREFLOP
        betting_hand._reset_betting_round_state()
        
        # Should preserve preflop betting state
        assert betting_hand.highest_bet == 50  # big_blind_cents
        assert betting_hand.last_full_raise_increment == 50
        
        # Player betting state should NOT reset for preflop
        for player in betting_hand.players:
            assert player.current_bet == 0  # Will be set by _post_blinds later
            assert player.has_checked_this_round is False
    
    def test_heads_up_edge_cases(self, betting_hand):
        """Test heads-up specific edge cases."""
        # Set up heads-up scenario
        betting_hand.players = betting_hand.players[:2]  # Keep only 2 players
        betting_hand.players[0].position = Position.BUTTON
        betting_hand.players[1].position = Position.BB
        
        # Preflop: BB should be able to check if no raise
        betting_hand.phase = Phase.PREFLOP
        betting_hand._reset_betting_round_state()
        
        # BB should have action (can check) because no one has bet
        bb_player = betting_hand.players[1]
        assert betting_hand._seat_still_has_action(bb_player) is True
        
        # Postflop: Button acts first
        betting_hand.phase = Phase.FLOP
        betting_hand._reset_betting_round_state()
        
        # Button should have action first
        button_player = betting_hand.players[0]
        assert betting_hand._seat_still_has_action(button_player) is True
    
    def test_integer_precision_no_floats(self, betting_hand):
        """Test that all amounts are integers (cents) with no float precision issues."""
        player = betting_hand.players[0]
        player.stack = 1000  # 1000 cents = $10.00
        
        # All calculations should be in integers
        validated = betting_hand.validate_action(player, ActionType.RAISE, 150)
        assert isinstance(validated.amount, int)
        assert validated.amount == 150
        
        betting_hand.apply_bet(player, validated)
        assert isinstance(betting_hand.highest_bet, int)
        assert betting_hand.highest_bet == 150
        assert isinstance(player.stack, int)
        assert player.stack == 850  # 1000 - 150
    
    def test_reopen_queue_rebuild(self, betting_hand):
        """Test that action queue rebuilds correctly after full raise."""
        # Set up initial state
        betting_hand.phase = Phase.FLOP
        betting_hand._reset_betting_round_state()
        
        # Player 1 makes first bet
        player1 = betting_hand.players[0]
        player1.position = Position.BUTTON
        validated1 = betting_hand.validate_action(player1, ActionType.RAISE, 100)
        betting_hand.apply_bet(player1, validated1)
        
        # Should reopen action
        assert betting_hand.last_aggressor == Position.BUTTON
        assert betting_hand.acted_since_last_full_raise == {Position.BUTTON}
        
        # Player 2 calls
        player2 = betting_hand.players[1]
        player2.position = Position.SB
        player2.stack = 1000
        validated2 = betting_hand.validate_action(player2, ActionType.CALL, 100)
        betting_hand.apply_call(player2, validated2)
        
        # Should be added to acted list
        assert Position.SB in betting_hand.acted_since_last_full_raise
        
        # Player 3 raises (full raise)
        player3 = betting_hand.players[2]
        player3.position = Position.BB
        player3.stack = 1000
        player3.current_bet = 100
        validated3 = betting_hand.validate_action(player3, ActionType.RAISE, 200)
        betting_hand.apply_raise(player3, validated3)
        
        # Should reopen action again
        assert betting_hand.last_aggressor == Position.BB
        assert betting_hand.acted_since_last_full_raise == {Position.BB}
        assert betting_hand.highest_bet == 200
        assert betting_hand.last_full_raise_increment == 100


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 