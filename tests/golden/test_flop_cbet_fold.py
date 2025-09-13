import pytest


def test_flop_cbet_fold_golden(run_named_script):
    out = run_named_script("flop_cbet_fold")

    # Final stacks - seat 0 should win uncontested pot
    # Pot: 0.25 + 0.50 + 1.50 + 1.50 = 3.75
    assert out["final_stacks"] == pytest.approx([102, 98.5, 99.5], abs=0.01)

    # Total pot should be 3.75
    assert out["total_pot"] == pytest.approx(3.75, abs=0.01)

    # Should have fold action and hand should end on flop
    rows = out["actions_rows"]
    actions = [row[2] for row in rows]
    assert "fold" in actions
    assert "raise" in actions
    
    # Should not have turn or river actions
    phases = [row[3] for row in rows]
    assert "turn" not in phases
    assert "river" not in phases 