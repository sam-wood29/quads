from unittest.mock import Mock, patch

import pytest

from quads.engine.enums import ActionType, Phase
from quads.engine.game_state import GameState, PlayerState
from quads.engine.phase_controller import PhaseController, street_is_settled


class TestPhaseController:
    """Test the Phase Controller FSM."""
    
    @pytest.fixture
    def mock_conn(self):
        """Create mock database connection."""
        conn = Mock()
        conn.cursor.return_value.execute.return_value = None
        conn.commit.return_value = None
        return conn
    
    @pytest.fixture
    def basic_game_state(self):
        """Create a basic GameState for testing."""
        players = [
            PlayerState(
                id=1, name="Player1", stack=2000, position="button",
                hole_cards=None, has_folded=False, is_all_in=False,
                current_bet=0, round_contrib=0, hand_contrib=0
            ),
            PlayerState(
                id=2, name="Player2", stack=2000, position="sb",
                hole_cards=None, has_folded=False, is_all_in=False,
                current_bet=0, round_contrib=0, hand_contrib=0
            ),
            PlayerState(
                id=3, name="Player3", stack=2000, position="bb",
                hole_cards=None, has_folded=False, is_all_in=False,
                current_bet=0, round_contrib=0, hand_contrib=0
            ),
        ]
        
        return GameState(
            hand_id=1,
            phase=Phase.DEAL.value,
            pot=0.0,
            community_cards=[],
            players=players,
            action_on=1,
            small_blind=0.25,
            big_blind=0.50,
            game_session_id=1,
            street_number=0
        )
    
    @pytest.fixture
    def phase_controller(self, basic_game_state, mock_conn):
        """Create a PhaseController instance."""
        return PhaseController(basic_game_state, mock_conn)
    
    def test_enter_phase_logs_and_sets_state(self, phase_controller):
        """Test that enter_phase logs and sets state correctly."""
        with patch('quads.engine.hand.log_action') as mock_log:  # Fix: patch in hand module
            mock_log.return_value = True
            
            # Test phase transition
            phase_controller.enter_phase(Phase.PREFLOP)
            
            # Verify state was updated
            assert phase_controller.state.phase == Phase.PREFLOP.value
            assert phase_controller.state.street_number == 1
            
            # Verify logging was called
            mock_log.assert_called_once()
            call_args = mock_log.call_args[1]
            assert call_args['action'] == ActionType.PHASE_ADVANCE.value
            assert call_args['phase'] == Phase.PREFLOP.value
    
    def test_start_betting_round_preflop(self, phase_controller):
        """Test betting round initialization for preflop."""
        phase_controller.state.phase = Phase.PREFLOP.value
        phase_controller.start_betting_round()
        
        # Check preflop-specific settings
        assert phase_controller.state.highest_bet == 0.50  # big_blind
        assert phase_controller.state.last_raise_increment == 0.50
        assert phase_controller.state.last_aggressor_seat is None
        assert len(phase_controller.state.acted_this_round) == 3
        assert len(phase_controller.state.committed_this_round) == 3
        assert len(phase_controller.state.actionable_seats) == 3
    
    def test_start_betting_round_postflop(self, phase_controller):
        """Test betting round initialization for postflop."""
        phase_controller.state.phase = Phase.FLOP.value
        phase_controller.start_betting_round()
        
        # Check postflop-specific settings
        assert phase_controller.state.highest_bet == 0.0  # No blinds on postflop
        assert phase_controller.state.last_raise_increment == 0.50
        assert phase_controller.state.last_aggressor_seat is None
        assert len(phase_controller.state.acted_this_round) == 3
        assert len(phase_controller.state.committed_this_round) == 3
    
    def test_street_is_settled_uncontested(self, phase_controller):
        """Test street settlement detection for uncontested pot."""
        # Set up uncontested scenario (2 players folded)
        phase_controller.state.players[1].has_folded = True
        phase_controller.state.players[2].has_folded = True
        
        assert phase_controller._street_is_settled() is True
        assert phase_controller._is_uncontested() is True
    
    def test_street_is_settled_all_matched_rotation(self, phase_controller):
        """Test street settlement when all players have matched and rotated."""
        # Set up scenario where everyone has acted and matched
        phase_controller.state.highest_bet = 1.0
        phase_controller.state.acted_this_round = {1: True, 2: True, 3: True}
        phase_controller.state.committed_this_round = {1: 1.0, 2: 1.0, 3: 1.0}
        
        assert phase_controller._street_is_settled() is True
        assert phase_controller._all_matched_and_rotated() is True
    
    def test_street_is_settled_all_in(self, phase_controller):
        """Test street settlement when all remaining players are all-in."""
        # Set up all-in scenario
        for player in phase_controller.state.players:
            player.is_all_in = True
        
        assert phase_controller._street_is_settled() is True
        assert phase_controller._all_remaining_all_in() is True
    
    def test_maybe_close_advances_correctly(self, phase_controller):
        """Test that maybe_close_street_and_advance advances phases correctly."""
        # Test PREFLOP → FLOP
        phase_controller.state.phase = Phase.PREFLOP.value
        phase_controller.state.players[1].has_folded = True
        phase_controller.state.players[2].has_folded = True
        
        with patch.object(phase_controller, 'enter_phase') as mock_enter:
            result = phase_controller.maybe_close_street_and_advance()
            
            assert result is True
            mock_enter.assert_called_with(Phase.SHOWDOWN)  # Should go to showdown due to uncontested
    
    def test_validate_transition_legal(self, phase_controller):
        """Test that legal transitions are allowed."""
        # These should not raise
        phase_controller._validate_transition(Phase.DEAL, Phase.PREFLOP)
        phase_controller._validate_transition(Phase.PREFLOP, Phase.FLOP)
        phase_controller._validate_transition(Phase.FLOP, Phase.TURN)
        phase_controller._validate_transition(Phase.TURN, Phase.RIVER)
        phase_controller._validate_transition(Phase.RIVER, Phase.SHOWDOWN)
    
    def test_validate_transition_illegal(self, phase_controller):
        """Test that illegal transitions raise ValueError."""
        with pytest.raises(ValueError, match="Illegal phase transition"):
            phase_controller._validate_transition(Phase.DEAL, Phase.FLOP)
        
        with pytest.raises(ValueError, match="Illegal phase transition"):
            phase_controller._validate_transition(Phase.PREFLOP, Phase.TURN)
    
    def test_street_number_mapping(self, phase_controller):
        """Test street number mapping for phases."""
        assert phase_controller._street_number_for(Phase.DEAL) == 0
        assert phase_controller._street_number_for(Phase.PREFLOP) == 1
        assert phase_controller._street_number_for(Phase.FLOP) == 2
        assert phase_controller._street_number_for(Phase.TURN) == 3
        assert phase_controller._street_number_for(Phase.RIVER) == 4
        assert phase_controller._street_number_for(Phase.SHOWDOWN) == 5
    
    def test_next_phase_after_street(self, phase_controller):
        """Test next phase calculation."""
        # Set the state to PREFLOP first
        phase_controller.state.phase = Phase.PREFLOP.value
        assert phase_controller._next_phase_after_street() == Phase.FLOP
        
        # Test other transitions
        phase_controller.state.phase = Phase.FLOP.value
        assert phase_controller._next_phase_after_street() == Phase.TURN
        
        phase_controller.state.phase = Phase.TURN.value
        assert phase_controller._next_phase_after_street() == Phase.RIVER
        
        phase_controller.state.phase = Phase.RIVER.value
        assert phase_controller._next_phase_after_street() == Phase.SHOWDOWN


class TestStreetSettlement:
    """Test street settlement helper function."""
    
    def test_street_is_settled_helper(self):
        """Test the standalone street_is_settled helper function."""
        # Create a minimal game state
        players = [
            PlayerState(
                id=1, name="Player1", stack=2000, position="button",
                hole_cards=None, has_folded=False, is_all_in=False,
                current_bet=0, round_contrib=0, hand_contrib=0
            ),
            PlayerState(
                id=2, name="Player2", stack=2000, position="sb",
                hole_cards=None, has_folded=True, is_all_in=False,
                current_bet=0, round_contrib=0, hand_contrib=0
            ),
        ]
        
        state = GameState(
            hand_id=1,
            phase=Phase.PREFLOP.value,
            pot=0.0,
            community_cards=[],
            players=players,
            action_on=1,
            small_blind=0.25,
            big_blind=0.50,
            game_session_id=1
        )
        
        # Should be settled (uncontested)
        assert street_is_settled(state) is True 