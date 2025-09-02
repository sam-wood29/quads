from unittest.mock import Mock

import pytest

from quads.deuces.deck import Deck
from quads.engine.enums import RaiseSetting
from quads.engine.hand import Hand
from quads.engine.money import to_cents
from quads.engine.player import Player, Position


class TestStateMoneyFields:
    """Test that cents fields are properly initialized and maintained."""
    
    @pytest.fixture
    def mock_players(self):
        """Create mock players for testing."""
        players = []
        for i in range(3):
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
        return players
    
    @pytest.fixture
    def mock_conn(self):
        """Create mock database connection."""
        conn = Mock()
        conn.cursor.return_value.execute.return_value = None
        conn.commit.return_value = None
        return conn
    
    @pytest.fixture
    def hand_with_cents(self, mock_players, mock_conn):
        """Create a Hand instance with cents fields."""
        deck = Deck()
        hand = Hand(
            players=mock_players,
            id=1,
            deck=deck,
            dealer_index=0,
            game_session_id=1,
            conn=mock_conn,
            script=None,
            raise_settings=RaiseSetting.STANDARD,
            small_blind=0.25,
            big_blind=0.50
        )
        
        # Set up positions
        mock_players[0].position = Position.BUTTON
        mock_players[1].position = Position.SB
        mock_players[2].position = Position.BB
        
        return hand
    
    def test_blind_conversion_uses_to_cents(self, hand_with_cents):
        """Test that blind conversion uses to_cents() function."""
        # Verify blinds are converted using to_cents
        expected_sb_cents = to_cents(0.25)
        expected_bb_cents = to_cents(0.50)
        
        assert hand_with_cents.small_blind_cents == expected_sb_cents
        assert hand_with_cents.big_blind_cents == expected_bb_cents
        assert hand_with_cents.small_blind_cents == 25
        assert hand_with_cents.big_blind_cents == 50
    
    def test_player_state_cents_fields_initialized(self, hand_with_cents):
        """Test that PlayerState cents fields are initialized from player data."""
        game_state = hand_with_cents.game_state
        
        for player_state in game_state.players:
            # Verify cents fields are initialized from player data
            assert player_state.stack_cents == player_state.stack
            assert player_state.current_bet_cents == player_state.current_bet
            assert player_state.committed_cents == player_state.hand_contrib
            
            # Verify they're integers (cents)
            assert isinstance(player_state.stack_cents, int)
            assert isinstance(player_state.current_bet_cents, int)
            assert isinstance(player_state.committed_cents, int)
    
    def test_game_state_cents_fields_initialized(self, hand_with_cents):
        """Test that GameState cents fields are initialized."""
        game_state = hand_with_cents.game_state
        
        # Verify pot_cents is initialized from pot
        assert game_state.pot_cents == game_state.pot
        assert isinstance(game_state.pot_cents, int)
        
        # Verify bet_to_call_cents is initialized to 0
        assert game_state.bet_to_call_cents == 0
        assert isinstance(game_state.bet_to_call_cents, int)
    
    def test_float_fields_dont_silently_change_cents(self, hand_with_cents):
        """Test that mutating old float fields doesn't silently change cents."""
        game_state = hand_with_cents.game_state
        player_state = game_state.players[0]
        
        # Store initial cents values
        initial_stack_cents = player_state.stack_cents
        initial_current_bet_cents = player_state.current_bet_cents
        initial_pot_cents = game_state.pot_cents
        
        # Modify float fields
        player_state.stack = 1500.0  # Change from 2000 to 1500
        player_state.current_bet = 100.0  # Change from 0 to 100
        game_state.pot = 250.0  # Change from 0 to 250
        
        # Verify cents fields are unchanged (they should be independent)
        assert player_state.stack_cents == initial_stack_cents
        assert player_state.current_bet_cents == initial_current_bet_cents
        assert game_state.pot_cents == initial_pot_cents
        
        # Verify the float fields did change
        assert player_state.stack == 1500.0
        assert player_state.current_bet == 100.0
        assert game_state.pot == 250.0
    
    def test_cents_fields_are_proper_types(self, hand_with_cents):
        """Test that all cents fields are proper Cents type (int)."""
        game_state = hand_with_cents.game_state
        
        # Check PlayerState cents fields
        for player_state in game_state.players:
            assert isinstance(player_state.stack_cents, int)
            assert isinstance(player_state.current_bet_cents, int)
            assert isinstance(player_state.committed_cents, int)
            
            # Verify they're non-negative
            assert player_state.stack_cents >= 0
            assert player_state.current_bet_cents >= 0
            assert player_state.committed_cents >= 0
        
        # Check GameState cents fields
        assert isinstance(game_state.pot_cents, int)
        assert isinstance(game_state.bet_to_call_cents, int)
        assert game_state.pot_cents >= 0
        assert game_state.bet_to_call_cents >= 0
    
    def test_blind_conversion_handles_edge_cases(self):
        """Test that blind conversion handles edge cases properly."""
        # Test with different blind values
        test_cases = [
            (0.01, 1),    # Minimum blind
            (0.25, 25),   # Quarter
            (1.00, 100), # Dollar
            (5.00, 500),  # Five dollars
        ]
        
        for blind_value, expected_cents in test_cases:
            # Create a minimal hand to test blind conversion
            players = [Mock(spec=Player) for _ in range(3)]
            for i, p in enumerate(players):
                p.id = i + 1
                p.name = f"Player{i+1}"
                p.stack = 2000
                p.seat_index = i
                p.current_bet = 0
                p.round_contrib = 0
                p.hand_contrib = 0
                p.has_folded = False
                p.all_in = False
                p.has_checked_this_round = False
                p.position = None
                p.hole_cards = None
                p.has_acted = False
            
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
                small_blind=blind_value,
                big_blind=blind_value * 2
            )
            
            assert hand.small_blind_cents == expected_cents
            assert hand.big_blind_cents == expected_cents * 2 