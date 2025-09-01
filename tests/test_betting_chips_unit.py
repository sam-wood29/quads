import pytest
from unittest.mock import Mock

from quads.engine.enums import ActionType, RaiseSetting
from quads.engine.hand import Hand
from quads.engine.money import Cents, to_cents
from quads.engine.player import Player, Position
from quads.engine.validated_action import ValidatedAction


class TestBettingChipsUnit:
    """Test betting chip movements in isolation."""
    
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
    def betting_hand(self, mock_players, mock_conn):
        """Create a Hand instance for betting tests."""
        from quads.deuces.deck import Deck
        
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
    
    def test_posting_blinds_increments_contributions(self, betting_hand):
        """Test that posting blinds increments contributions correctly."""
        # Set up players for blind posting
        players = betting_hand.players
        players[1].stack = 1000  # SB player
        players[2].stack = 1000  # BB player
        
        # Post blinds
        betting_hand._post_blinds()
        
        # Check SB player
        sb_player = players[1]
        expected_sb = to_cents(0.25)  # 25 cents
        assert sb_player.hand_contrib == expected_sb
        assert sb_player.round_contrib == expected_sb
        assert sb_player.current_bet == expected_sb
        assert sb_player.stack == 1000 - expected_sb
        
        # Check BB player
        bb_player = players[2]
        expected_bb = to_cents(0.50)  # 50 cents
        assert bb_player.hand_contrib == expected_bb
        assert bb_player.round_contrib == expected_bb
        assert bb_player.current_bet == expected_bb
        assert bb_player.stack == 1000 - expected_bb
        
        # Check pot manager contributions
        assert betting_hand.pot_manager.get_player_contribution(sb_player.id) == expected_sb
        assert betting_hand.pot_manager.get_player_contribution(bb_player.id) == expected_bb
        assert betting_hand.pot_manager.total_table_cents() == expected_sb + expected_bb
    
    def test_raise_updates_only_delta(self, betting_hand):
        """Test that a raise updates only the delta, not the whole amount."""
        player = betting_hand.players[0]
        player.stack = 1000
        player.current_bet = 0
        
        # First, post blinds to establish a bet
        betting_hand._post_blinds()
        actual_current_bet = player.current_bet
        raise_amount = 200
        expected_delta = raise_amount - actual_current_bet
        
        # Player raises to 200 cents (from 0)
        
        validated = ValidatedAction(
            action_type=ActionType.RAISE,
            amount=raise_amount,
            is_full_raise=True,
            raise_increment=raise_amount,
            reopen_action=True
        )
        
        betting_hand.apply_raise(player, validated)
        print("player current bet")
        print(player.current_bet)
        print("player current stack")
        print(player.stack)
        print("raise amount")
        print(raise_amount)
        
        print("expected delta")
        print(expected_delta)
        assert player.stack == (1000 - expected_delta)
        assert player.hand_contrib == expected_delta
        assert player.current_bet == raise_amount
        
        # Check pot manager
        assert betting_hand.pot_manager.get_player_contribution(player.id) == expected_delta
        assert betting_hand.pot_manager.total_table_cents() == to_cents(0.25) + to_cents(0.50) + expected_delta
    
    def test_call_updates_only_call_amount(self, betting_hand):
        """Test that a call updates only the call amount."""
        # Set up scenario: BB is 50, player calls
        betting_hand._post_blinds()
        
        player = betting_hand.players[0]
        player.stack = 1000
        player.current_bet = 0
        
        # Player calls the BB (50 cents)
        call_amount = to_cents(0.50)  # 50 cents
        validated = ValidatedAction(
            action_type=ActionType.CALL,
            amount=call_amount,
            is_full_raise=False,
            raise_increment=0,
            reopen_action=False
        )
        
        betting_hand.apply_call(player, validated)
        
        # Check that only the call amount was taken
        assert player.stack == 1000 - call_amount
        assert player.hand_contrib == call_amount
        assert player.current_bet == call_amount
        
        # Check pot manager
        assert betting_hand.pot_manager.get_player_contribution(player.id) == call_amount
    
    def test_fold_marks_player_in_pot_manager(self, betting_hand):
        """Test that fold marks player as folded in pot manager."""
        player = betting_hand.players[0]
        
        validated = ValidatedAction(
            action_type=ActionType.FOLD,
            amount=0,
            is_full_raise=False,
            raise_increment=0,
            reopen_action=False
        )
        
        betting_hand.apply_fold(player, validated)
        
        # Check that player is marked as folded
        assert player.has_folded is True
        assert betting_hand.pot_manager.is_player_folded(player.id) is True
    
    def test_uncalled_bet_returns_exact_overage(self, betting_hand):
        """Test that uncalled bet returns exactly the overage to the bettor."""
        # Set up scenario: Player 1 bets 200, everyone folds
        betting_hand._post_blinds()
        
        player1 = betting_hand.players[0]
        player2 = betting_hand.players[1]
        player3 = betting_hand.players[2]
        
        # Player 1 bets 200 cents
        player1.stack = 1000
        player1.current_bet = 0
        
        bet_amount = 200
        validated = ValidatedAction(
            action_type=ActionType.RAISE,
            amount=bet_amount,
            is_full_raise=True,
            raise_increment=bet_amount,
            reopen_action=True
        )
        
        betting_hand.apply_raise(player1, validated)
        
        # Everyone else folds
        for player in [player2, player3]:
            fold_validated = ValidatedAction(
                action_type=ActionType.FOLD,
                amount=0,
                is_full_raise=False,
                raise_increment=0,
                reopen_action=False
            )
            betting_hand.apply_fold(player, fold_validated)
        
        # Calculate expected uncalled amount
        # BB was 50, so uncalled amount is 200 - 50 = 150
        expected_uncalled = bet_amount - to_cents(0.50)  # 200 - 50 = 150
        
        # Return uncalled bet
        betting_hand._return_uncalled_bet(player1)
        
        # Check that exact overage was returned
        assert player1.stack == 1000 - bet_amount + expected_uncalled  # 1000 - 200 + 150 = 950
        assert player1.hand_contrib == bet_amount - expected_uncalled  # 200 - 150 = 50
        
        # Check pot manager
        assert betting_hand.pot_manager.get_player_contribution(player1.id) == bet_amount - expected_uncalled
        assert betting_hand.pot_manager.total_table_cents() == to_cents(0.25) + to_cents(0.50) + (bet_amount - expected_uncalled)
    
    def test_multiple_actions_accumulate_correctly(self, betting_hand):
        """Test that multiple actions accumulate contributions correctly."""
        betting_hand._post_blinds()
        
        player = betting_hand.players[0]
        player.stack = 1000
        player.current_bet = 0
        
        # Player calls BB (50 cents)
        call_validated = ValidatedAction(
            action_type=ActionType.CALL,
            amount=to_cents(0.50),
            is_full_raise=False,
            raise_increment=0,
            reopen_action=False
        )
        betting_hand.apply_call(player, call_validated)
        
        # Player raises to 200 cents (additional 150)
        raise_validated = ValidatedAction(
            action_type=ActionType.RAISE,
            amount=200,
            is_full_raise=True,
            raise_increment=150,
            reopen_action=True
        )
        betting_hand.apply_raise(player, raise_validated)
        
        # Check total contribution
        expected_total = to_cents(0.50) + 150  # 50 + 150 = 200
        assert player.hand_contrib == expected_total
        assert betting_hand.pot_manager.get_player_contribution(player.id) == expected_total
        
        # Check stack reduction
        assert player.stack == 1000 - expected_total
    
    def test_all_in_handles_stack_limits(self, betting_hand):
        """Test that all-in actions handle stack limits correctly."""
        betting_hand._post_blinds()
        
        player = betting_hand.players[0]
        player.stack = 100  # Small stack
        player.current_bet = 0  # Reset for clean test
        
        raise_validated = ValidatedAction(
            action_type=ActionType.RAISE,
            amount=200,  # Target amount
            is_full_raise=False,
            raise_increment=200,
            reopen_action=False
        )
        
        # This should succeed as an all-in
        betting_hand.apply_raise(player, raise_validated)
        
        # Should be all-in with correct amounts
        assert player.all_in is True
        assert player.stack == 0
        assert player.current_bet == 100  # Capped to stack
        assert player.hand_contrib == 100
    
    def test_pot_manager_invariant_maintained(self, betting_hand):
        """Test that pot manager invariant is maintained throughout betting."""
        betting_hand._post_blinds()
        
        # Verify initial state
        total_contributions = sum(betting_hand.pot_manager.contributed.values())
        assert total_contributions == to_cents(0.25) + to_cents(0.50)
        
        # Add some betting
        player = betting_hand.players[0]
        player.stack = 1000
        player.current_bet = 0
        
        call_validated = ValidatedAction(
            action_type=ActionType.CALL,
            amount=to_cents(0.50),
            is_full_raise=False,
            raise_increment=0,
            reopen_action=False
        )
        betting_hand.apply_call(player, call_validated)
        
        # Verify invariant still holds
        total_contributions = sum(betting_hand.pot_manager.contributed.values())
        expected_total = to_cents(0.25) + to_cents(0.50) + to_cents(0.50)
        assert total_contributions == expected_total
        assert betting_hand.pot_manager.total_table_cents() == expected_total 