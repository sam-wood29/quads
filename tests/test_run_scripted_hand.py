import pytest
from quads.engine.run_scripted_harness import run_script


def test_run_scripted_hand_basic():
    """Test running a basic scripted hand."""
    script = {
        "small_blind": 0.25,
        "big_blind": 0.50,
        "start_stacks": [100.0, 100.0],
        "dealer_index": 0,
        "hole_cards": [
            ["As", "Kd"],  # seat 0
            ["7h", "7c"]   # seat 1
        ],
        "board": ["2d", "9s", "Jh", "5c", "3d"],
        "preflop": {
            "actions": {
                0: [{"type": "raise", "amount": 1.0}],
                1: [{"type": "call"}]
            }
        },
        "flop": {
            "actions": {
                1: [{"type": "check"}],
                0: [{"type": "check"}]
            }
        },
        "turn": {
            "actions": {
                1: [{"type": "check"}],
                0: [{"type": "check"}]
            }
        },
        "river": {
            "actions": {
                1: [{"type": "check"}],
                0: [{"type": "check"}]
            }
        }
    }
    
    result = run_script(script)
    
    # Check that we got results
    assert "final_stacks" in result
    assert "total_pot" in result
    assert "actions_rows" in result
    
    # Check that actions were logged
    assert len(result["actions_rows"]) > 0
    
    # Check that blinds were posted
    actions = [row[2] for row in result["actions_rows"]]  # action column
    assert "post_small_blind" in actions
    assert "post_big_blind" in actions


def test_run_scripted_hand_simple():
    """Test running a very simple hand - just blinds and check/check."""
    script = {
        "small_blind": 0.25,
        "big_blind": 0.50,
        "start_stacks": [100.0, 100.0],
        "dealer_index": 0,
        "hole_cards": [
            ["As", "Kd"],  # seat 0
            ["7h", "7c"]   # seat 1
        ],
        "board": ["2d", "9s", "Jh", "5c", "3d"],
        "preflop": {
            "actions": {
                0: [{"type": "call"}],  # SB Calls 
                1: [{"type": "check"}]   # BB checks
            }
        },
        "flop": {
            "actions": {
                1: [{"type": "check"}],
                0: [{"type": "check"}]
            }
        },
        "turn": {
            "actions": {
                1: [{"type": "check"}],
                0: [{"type": "check"}]
            }
        },
        "river": {
            "actions": {
                1: [{"type": "check"}],
                0: [{"type": "check"}]
            }
        }
    }
    
    result = run_script(script)
    
    # Basic checks
    assert "final_stacks" in result
    assert "total_pot" in result
    assert "actions_rows" in result
    
    # Should have at least blind postings
    assert len(result["actions_rows"]) >= 2