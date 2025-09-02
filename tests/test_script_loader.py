import pytest
from quads.engine.script_loader import load_script, _normalize_keys, get_script_actions_by_seat, validate_script_structure


def test_normalize_string_keys():
    """Test normalization of string keys to integers."""
    raw_script = {
        "small_blind": 0.25,
        "big_blind": 0.50,
        "start_stacks": [100.0, 100.0],
        "dealer_index": 0,
        "hole_cards": [["As", "Kd"], ["7h", "7c"]],
        "board": ["2d", "9s", "Jh", "5c", "3d"],
        "preflop": {
            "actions": {
                "0": [{"type": "raise", "amount": 1.0}],
                "1": [{"type": "call"}]
            }
        },
        "flop": {
            "actions": {
                "1": [{"type": "check"}],
                "0": [{"type": "bet", "amount": 0.75}]
            }
        }
    }
    
    normalized = _normalize_keys(raw_script)
    
    # Check that string keys became integers
    assert normalized["preflop"]["actions"][0] == [{"type": "raise", "amount": 1.0}]
    assert normalized["preflop"]["actions"][1] == [{"type": "call"}]
    assert normalized["flop"]["actions"][0] == [{"type": "bet", "amount": 0.75}]
    assert normalized["flop"]["actions"][1] == [{"type": "check"}]


def test_normalize_integer_keys():
    """Test that integer keys remain integers."""
    raw_script = {
        "small_blind": 0.25,
        "big_blind": 0.50,
        "start_stacks": [100.0, 100.0],
        "dealer_index": 0,
        "hole_cards": [["As", "Kd"], ["7h", "7c"]],
        "board": ["2d", "9s", "Jh", "5c", "3d"],
        "preflop": {
            "actions": {
                0: [{"type": "raise", "amount": 1.0}],
                1: [{"type": "call"}]
            }
        }
    }
    
    normalized = _normalize_keys(raw_script)
    
    # Check that integer keys remain integers
    assert normalized["preflop"]["actions"][0] == [{"type": "raise", "amount": 1.0}]
    assert normalized["preflop"]["actions"][1] == [{"type": "call"}]


def test_normalize_missing_phases():
    """Test that missing phases get default empty actions."""
    raw_script = {
        "small_blind": 0.25,
        "big_blind": 0.50,
        "start_stacks": [100.0, 100.0],
        "dealer_index": 0,
        "hole_cards": [["As", "Kd"], ["7h", "7c"]],
        "board": ["2d", "9s", "Jh", "5c", "3d"],
        "preflop": {
            "actions": {
                "0": [{"type": "raise", "amount": 1.0}]
            }
        }
        # Missing flop, turn, river
    }
    
    normalized = _normalize_keys(raw_script)
    
    # Check that missing phases get empty actions
    assert normalized["flop"]["actions"] == {}
    assert normalized["turn"]["actions"] == {}
    assert normalized["river"]["actions"] == {}


def test_get_script_actions_by_seat():
    """Test extracting actions by seat across all phases."""
    script = {
        "preflop": {
            "actions": {
                0: [{"type": "raise", "amount": 1.0}],
                1: [{"type": "call"}]
            }
        },
        "flop": {
            "actions": {
                1: [{"type": "check"}],
                0: [{"type": "bet", "amount": 0.75}]
            }
        },
        "turn": {
            "actions": {}
        },
        "river": {
            "actions": {}
        }
    }
    
    actions_by_seat = get_script_actions_by_seat(script)
    
    assert actions_by_seat[0] == [
        {"type": "raise", "amount": 1.0},
        {"type": "bet", "amount": 0.75}
    ]
    assert actions_by_seat[1] == [
        {"type": "call"},
        {"type": "check"}
    ]


def test_validate_script_structure():
    """Test script structure validation."""
    valid_script = {
        "small_blind": 0.25,
        "big_blind": 0.50,
        "start_stacks": [100.0, 100.0],
        "dealer_index": 0,
        "hole_cards": [["As", "Kd"], ["7h", "7c"]],
        "board": ["2d", "9s", "Jh", "5c", "3d"]
    }
    
    # Should not raise
    assert validate_script_structure(valid_script) is True
    
    # Test missing field
    invalid_script = dict(valid_script)
    del invalid_script["small_blind"]
    
    with pytest.raises(ValueError, match="Script missing required field: small_blind"):
        validate_script_structure(invalid_script)
    
    # Test invalid hole_cards
    invalid_script = dict(valid_script)
    invalid_script["hole_cards"] = [["As"], ["7h", "7c"]]  # First player has only 1 card
    
    with pytest.raises(ValueError, match="hole_cards\\[0\\] must be a list of 2 cards"):
        validate_script_structure(invalid_script)
    
    # Test invalid board
    invalid_script = dict(valid_script)
    invalid_script["board"] = ["2d", "9s", "Jh"]  # Only 3 cards
    
    with pytest.raises(ValueError, match="board must be a list of 5 cards"):
        validate_script_structure(invalid_script)