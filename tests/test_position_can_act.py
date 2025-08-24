
from quads.engine.player import Position
from tests.fakes import FakeGameState, FakePlayerState


class TestPositionCanAct:
    """Test the position action validation predicates."""

    def setup_method(self):
        """Set up test fixtures."""
        # Create a minimal Hand-like object for testing
        class MockHand:
            def __init__(self, game_state):
                self.game_state = game_state
                self.highest_bet = game_state.current_bet
            
            def _position_can_act(self, pos):
                # Find the player with this position
                player_state = self.game_state.players_by_position.get(pos)
                if not player_state:
                    return False
                
                if player_state.has_folded:
                    return False
                if player_state.is_all_in:
                    return False
                
                # If there is a bet, seat must have option to act
                return self._seat_still_has_action(player_state)
            
            def _seat_still_has_action(self, player_state):
                # If no bet to call, player can check (unless they already have)
                if self.highest_bet == 0:
                    return not player_state.has_checked_this_round
                
                # Facing a bet - check if they need to call
                need_to_call = self.highest_bet - player_state.bet_this_round
                return need_to_call > 0
        
        self.MockHand = MockHand

    def test_folded_cannot_act(self):
        """Test that folded players cannot act."""
        gs = FakeGameState(0.0, {
            Position.UTG: FakePlayerState(has_folded=True),
        })
        h = self.MockHand(gs)
        
        assert h._position_can_act(Position.UTG) is False

    def test_allin_cannot_act(self):
        """Test that all-in players cannot act."""
        gs = FakeGameState(0.0, {
            Position.CO: FakePlayerState(is_all_in=True),
        })
        h = self.MockHand(gs)
        
        assert h._position_can_act(Position.CO) is False

    def test_no_bet_can_check_if_not_checked(self):
        """Test that players can check when no bet and haven't checked."""
        gs = FakeGameState(0.0, {
            Position.HJ: FakePlayerState(has_checked_this_round=False),
        })
        h = self.MockHand(gs)
        
        assert h._position_can_act(Position.HJ) is True

    def test_no_bet_cannot_check_if_already_checked(self):
        """Test that players cannot check twice when no bet."""
        gs = FakeGameState(0.0, {
            Position.HJ: FakePlayerState(has_checked_this_round=True),
        })
        h = self.MockHand(gs)
        
        assert h._position_can_act(Position.HJ) is False

    def test_facing_bet_and_already_matched(self):
        """Test that players facing a bet they've already matched cannot act."""
        gs = FakeGameState(current_bet=50.0, players_by_position={
            Position.CO: FakePlayerState(bet_this_round=50.0),
        })
        h = self.MockHand(gs)
        
        # Should not have action if already matched
        assert h._position_can_act(Position.CO) is False

    def test_facing_bet_not_matched(self):
        """Test that players facing a bet they haven't matched can act."""
        gs = FakeGameState(current_bet=50.0, players_by_position={
            Position.CO: FakePlayerState(bet_this_round=20.0),
        })
        h = self.MockHand(gs)
        
        assert h._position_can_act(Position.CO) is True

    def test_position_not_in_game_state(self):
        """Test that positions not in the game state cannot act."""
        gs = FakeGameState(0.0, {})  # Empty game state
        h = self.MockHand(gs)
        
        assert h._position_can_act(Position.UTG) is False

    def test_edge_case_zero_bet(self):
        """Test edge case where bet amount is exactly zero."""
        gs = FakeGameState(current_bet=0.0, players_by_position={
            Position.BB: FakePlayerState(bet_this_round=0.0, has_checked_this_round=False),
        })
        h = self.MockHand(gs)
        
        assert h._position_can_act(Position.BB) is True