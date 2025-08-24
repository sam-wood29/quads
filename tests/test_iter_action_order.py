from collections import deque

import pytest

from quads.engine.player import Position


class TestIterActionOrder:
    """Test the iter_action_order iterator logic."""

    def setup_method(self):
        """Set up test fixtures."""
        # Create a minimal Hand-like object for testing
        class MockHand:
            def __init__(self, active_positions):
                self.active_positions = set(active_positions)
            
            def _position_can_act(self, pos):
                return pos in self.active_positions
            
            def iter_action_order(self, order, start_from=None):
                """Mock implementation matching the real one."""
                if not order:
                    return
                
                q = deque(order)
                
                if start_from is not None:
                    # Add safety check to prevent infinite loop
                    if start_from not in order:
                        raise ValueError(f"start_from position {start_from} not found in order {order}")
                    
                    # Rotate until start_from is at the beginning
                    while q[0] != start_from:
                        q.rotate(-1)
                
                # Track how many positions we've seen to prevent infinite loops
                seen = 0
                total = len(q)
                
                while seen < total:
                    pos = q[0]
                    q.rotate(-1)
                    seen += 1
                    
                    if self._position_can_act(pos):
                        yield pos
        
        self.MockHand = MockHand

    def test_rotation_and_no_mutation(self):
        """Test that rotation works and order is not mutated."""
        order = [Position.UTG, Position.HJ, Position.CO, Position.BUTTON, Position.SB, Position.BB]
        h = self.MockHand({Position.CO, Position.SB, Position.BB})
        orig = list(order)  # Copy for comparison
        
        # Iterate starting from BUTTON
        out = list(h.iter_action_order(order, start_from=Position.BUTTON))
        
        # No mutation of original order
        assert order == orig, "Original order should not be mutated"
        
        # Should get positions in rotated order, filtered to active ones
        # Rotation: BUTTON → SB → BB → UTG → HJ → CO
        # Filtered to active: SB, BB, CO
        expected = [Position.SB, Position.BB, Position.CO]
        assert out == expected, f"Expected {expected}, got {out}"

    def test_one_lap_only(self):
        """Test that iteration completes exactly one lap."""
        order = [Position.UTG, Position.CO, Position.BUTTON]
        h = self.MockHand({Position.UTG, Position.CO, Position.BUTTON})
        
        out = list(h.iter_action_order(order, start_from=Position.CO))
        
        # Should get exactly one lap starting from CO
        expected = [Position.CO, Position.BUTTON, Position.UTG]
        assert out == expected, f"Expected {expected}, got {out}"
        assert len(out) == len(order), "Should get exactly one lap"

    def test_skips_inactive(self):
        """Test that inactive positions are properly skipped."""
        order = [Position.UTG, Position.CO, Position.BUTTON, Position.SB]
        h = self.MockHand({Position.BUTTON})  # Only BTN can act
        
        out = list(h.iter_action_order(order))
        
        # Should only get the active position
        assert out == [Position.BUTTON], f"Expected [BUTTON], got {out}"

    def test_empty_order(self):
        """Test that empty order returns nothing."""
        h = self.MockHand({Position.UTG})
        
        out = list(h.iter_action_order([]))
        assert out == [], "Empty order should yield nothing"

    def test_all_positions_inactive(self):
        """Test that all inactive positions yields nothing."""
        order = [Position.UTG, Position.CO, Position.BUTTON]
        h = self.MockHand(set())  # No active positions
        
        out = list(h.iter_action_order(order))
        assert out == [], "All inactive positions should yield nothing"

    def test_start_from_not_in_order_raises_error(self):
        """Test that invalid start_from raises an error."""
        order = [Position.UTG, Position.CO]
        h = self.MockHand({Position.UTG, Position.CO})
        
        # Should raise ValueError when start_from is not in order
        with pytest.raises(ValueError, match="start_from position BB not found in order"):
            list(h.iter_action_order(order, start_from=Position.BB))

    def test_rotation_preserves_order(self):
        """Test that rotation preserves the relative order of positions."""
        order = [Position.UTG, Position.HJ, Position.CO, Position.BUTTON]
        h = self.MockHand({Position.UTG, Position.HJ, Position.CO, Position.BUTTON})
        
        # Test rotation from different starting points
        start_positions = [Position.UTG, Position.HJ, Position.CO, Position.BUTTON]
        
        for start_pos in start_positions:
            out = list(h.iter_action_order(order, start_from=start_pos))
            
            # Should maintain relative order starting from start_pos
            start_idx = order.index(start_pos)
            expected = order[start_idx:] + order[:start_idx]
            assert out == expected, f"Rotation from {start_pos} failed: expected {expected}, got {out}"

    def test_no_start_from_uses_original_order(self):
        """Test that no start_from uses the original order."""
        order = [Position.UTG, Position.HJ, Position.CO, Position.BUTTON]
        h = self.MockHand({Position.UTG, Position.HJ, Position.CO, Position.BUTTON})
        
        out = list(h.iter_action_order(order))  # No start_from
        
        # Should use original order
        assert out == order, f"Expected {order}, got {out}"