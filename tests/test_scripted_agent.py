from unittest.mock import Mock

import pytest

from quads.engine.enums import ActionType
from quads.engine.scripted_agent import ScriptedAgent
from quads.engine.validated_action import ValidatedAction


def test_scripted_agent_sequence():
    """Test that ScriptedAgent yields actions in exact sequence."""
    # Mock validation function that records calls
    validation_calls = []
    
    def mock_validate(player, action_type, amount_cents):
        validation_calls.append((action_type, amount_cents))
        return ValidatedAction(
            action_type=action_type,
            amount=amount_cents,
            is_full_raise=False,
            raise_increment=0,
            reopen_action=False
        )
    
    # Create actions
    actions = [
        {"type": "check"},
        {"type": "raise", "amount": 1.50},
        {"type": "fold"}
    ]
    
    agent = ScriptedAgent(actions, mock_validate)
    
    # Mock player
    player = Mock()
    
    # Get actions
    result1 = agent.decide(player)
    assert result1.action_type == ActionType.CHECK
    assert result1.amount == 0
    
    result2 = agent.decide(player)
    assert result2.action_type == ActionType.RAISE
    assert result2.amount == 150  # 1.50 dollars = 150 cents
    
    result3 = agent.decide(player)
    assert result3.action_type == ActionType.FOLD
    assert result3.amount == 0
    
    # Verify validation was called with correct args
    assert validation_calls == [
        (ActionType.CHECK, 0),
        (ActionType.RAISE, 150),
        (ActionType.FOLD, 0)
    ]


def test_scripted_agent_exhaustion():
    """Test that ScriptedAgent raises when out of actions."""
    actions = [{"type": "check"}]
    agent = ScriptedAgent(actions, Mock())
    
    # First call should work
    player = Mock()
    agent.decide(player)
    
    # Second call should raise
    with pytest.raises(RuntimeError, match="ScriptedAgent ran out of actions"):
        agent.decide(player)


def test_scripted_agent_bet_mapping():
    """Test that 'bet' action maps to ActionType.RAISE."""
    def mock_validate(player, action_type, amount_cents):
        return ValidatedAction(
            action_type=action_type,
            amount=amount_cents,
            is_full_raise=False,
            raise_increment=0,
            reopen_action=False
        )
    
    actions = [{"type": "bet", "amount": 2.0}]
    agent = ScriptedAgent(actions, mock_validate)
    
    player = Mock()
    result = agent.decide(player)
    
    assert result.action_type == ActionType.RAISE
    assert result.amount == 200  # 2.0 dollars = 200 cents


def test_scripted_agent_unknown_action():
    """Test that unknown action types raise ValueError."""
    actions = [{"type": "invalid_action"}]
    agent = ScriptedAgent(actions, Mock())
    
    player = Mock()
    with pytest.raises(ValueError, match="Unknown action type: invalid_action"):
        agent.decide(player)