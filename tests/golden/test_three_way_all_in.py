import pytest


def test_three_way_all_in_golden(run_named_script):
    out = run_named_script("three_way_all_in")

    # Final stacks - seat 2 (AA) should win both pots
    # Main pot: 40*3 = 120, side pot: (80-40)*2 = 80
    # Seat 0: 80 - 80 = 0, Seat 1: 40 - 40 = 0, Seat 2: 120 + 200 = 320
    assert out["final_stacks"] == pytest.approx([0.0, 0.0, 320.0], abs=0.01)

    # Total pot should be 200 (all chips in play)
    assert out["total_pot"] == pytest.approx(200.0, abs=0.01)

    # Should have all-in actions
    rows = out["actions_rows"]
    actions = [row[2] for row in rows]
    assert "raise" in actions
    assert "call" in actions
    assert len(actions) >= 5  # At least blinds + all-in actions 