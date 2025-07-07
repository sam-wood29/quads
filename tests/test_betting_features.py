import pytest
from quads.engine.hand import Hand
from quads.engine.player import Player
from quads.engine.base_controller import GlobalScriptController
from quads.engine.extras import Action
from pprint import pformat


class TestBettingStructure:
    """Test core betting structure features."""

    def test_min_raise_enforcement(self):
        """Test that minimum raise rules are enforced."""
        # Setup players
        players = [
            Player(name="alice", stack=100.0),
            Player(name="bob", stack=100.0),
            Player(name="charlie", stack=100.0)
        ]
        
        # Set up controller with script
        script = [
            ("alice", Action.RAISE, 2.0),  # First raise to 2.0 (valid)
            ("bob", Action.RAISE, 3.0),    # Should fail - min raise is 2.0
            ("bob", Action.RAISE, 4.0),    # Should pass - min raise is 2.0
        ]
        
        controller = GlobalScriptController(script=script)
        for p in players:
            p.controller=controller
        
        for i, p in enumerate(players):
            p.seat_index = i
        
        # Create hand with min_raise=2.0
        hand = Hand(players=players, 
                    small_blind=0.25,
                    big_blind=0.50,
                    dealer_index=0,
                    hand_id=1,
                    )
        
        # Play the hand
        result = hand.play()
        
        # Check the action log to see what actually happened
        action_log = hand.action_log
        hand.logger.info('aciton log....')
        hand.logger.info(pformat(action_log))
        
        
        # Find bob's actions
        bob_actions = [entry for entry in action_log if entry.get('player') == 'bob']
        
        # Verify that bob's invalid raise (3.0) was rejected
        # The system should have defaulted to fold or call
        assert len(bob_actions) > 0, "Bob should have taken some action"
        
        # Check that bob didn't successfully raise to 3.0
        bob_raises = [entry for entry in bob_actions if entry['action'] == 'RAISE']
        for raise_action in bob_raises:
            assert raise_action['amount'] != 3.0, f"Bob should not have been able to raise to 3.0: {raise_action}"
        
        # Verify the hand completed successfully
        assert result is not None
        assert "winners" in result

    def test_max_raise_limit(self):
        """Test maximum raise limits."""
        players = [
            Player(name="alice", stack=100.0),
            Player(name="bob", stack=100.0),
        ]
        
        script = [
            ("alice", Action.RAISE, 5.0),  # Should work
            ("bob", Action.RAISE, 10.0),   # Should fail if max_raise=5.0
        ]
        
        for player in players:
            player.controller = GlobalScriptController(script)
        
        # Create hand with max_raise=5.0
        hand = Hand(players=players, max_raise=5.0)
        
        result = hand.play()
        assert result is not None

    def test_no_limit_raise(self):
        """Test that no-limit raises work when max_raise=None."""
        players = [
            Player(name="alice", stack=100.0),
            Player(name="bob", stack=100.0),
        ]
        
        script = [
            ("alice", Action.RAISE, 50.0),  # Large raise should work
            ("bob", Action.CALL, None),
        ]
        
        for player in players:
            player.controller = GlobalScriptController(script)
        
        # Create hand with no max_raise (no limit)
        hand = Hand(players=players, max_raise=None)
        
        result = hand.play()
        assert result is not None

    def test_valid_actions_generation(self):
        """Test that valid actions are correctly generated."""
        players = [
            Player(name="alice", stack=100.0),
            Player(name="bob", stack=100.0),
        ]
        
        hand = Hand(players=players, min_raise=2.0)
        
        # Test valid actions for a player
        player = players[0]
        valid_actions = hand._get_valid_actions(player, 0, 0)
        
        # Should always be able to fold
        assert Action.FOLD in valid_actions['actions']
        
        # Should be able to check when no bet
        assert Action.CHECK in valid_actions['actions']
        
        # Should be able to bet/raise when no bet
        assert Action.BET in valid_actions['actions']
        assert Action.RAISE in valid_actions['actions']

    def test_min_raise_calculation(self):
        """Test minimum raise calculation logic."""
        hand = Hand(players=[], min_raise=2.0)
        
        # First raise of the round
        min_raise = hand._calculate_min_raise(0)
        assert min_raise == 2.0  # Should be min_raise when no previous raise
        
        # Subsequent raise
        hand.last_raise_amount = 3.0
        min_raise = hand._calculate_min_raise(5.0)
        assert min_raise == 8.0  # Should be highest_bet + last_raise_amount

    def test_action_validation(self):
        """Test that action validation works correctly."""
        players = [Player(name="alice", stack=100.0)]
        hand = Hand(players=players, min_raise=2.0)
        
        # Test valid raise
        valid_actions = {
            'actions': [Action.RAISE],
            'min_raise': 2.0,
            'max_raise': 100.0
        }
        
        # Valid raise
        assert hand._validate_action(Action.RAISE, 4.0, valid_actions, players[0])
        
        # Invalid raise (too small)
        assert not hand._validate_action(Action.RAISE, 1.0, valid_actions, players[0])

# 1. Test Betting Structure & limits

