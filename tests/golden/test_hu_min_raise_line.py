import pytest


def test_hu_min_raise_line_golden(run_named_script):
    out = run_named_script("hu_min_raise_line")

    # Final stacks (in dollars since we convert back in harness)
    assert out["final_stacks"] == pytest.approx([99.0, 101.0], abs=0.01)

    # Pot (should be 2.0 - the raise and call)
    assert out["total_pot"] == pytest.approx(2.0, abs=0.01)

    # Ordered actions snapshot (action, phase) for first N rows
    rows = out["actions_rows"]
    assert [(r[2], r[3]) for r in rows[:6]] == [
        ("post_small_blind", "deal"),
        ("post_big_blind", "deal"),
        ("deal_hole", "deal"),
        ("deal_hole", "deal"),
        ("raise", "preflop"),
        ("call", "preflop"),
    ]
