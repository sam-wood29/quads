import pytest

from quads.engine.betting_order import BettingOrder
from quads.engine.enums import Phase  # Fixed import
from quads.engine.player import Position


class TestBettingOrderTable:
    """Test the table-driven betting order configuration."""

    @pytest.mark.parametrize("num_players,phase,button,expected", [
        # Heads-up: preflop SB first, then BB
        (2, Phase.PREFLOP, Position.BUTTON, [Position.SB, Position.BB]),
        # Heads-up: postflop BB first (left of button)
        (2, Phase.FLOP, Position.BUTTON, [Position.BB, Position.SB]),
        (2, Phase.TURN, Position.BUTTON, [Position.BB, Position.SB]),
        (2, Phase.RIVER, Position.BUTTON, [Position.BB, Position.SB]),
        
        # 3-handed scenarios
        (3, Phase.PREFLOP, Position.BUTTON, [Position.BUTTON, Position.SB, Position.BB]),
        (3, Phase.FLOP, Position.BUTTON, [Position.SB, Position.BB, Position.BUTTON]),
        
        # 6-max preflop sample (UTG → ... → BB)
        (6, Phase.PREFLOP, Position.BUTTON,
         [Position.UTG, Position.HJ, Position.CO, Position.BUTTON, Position.SB, Position.BB]),
        # 6-max postflop (SB first, BTN last)
        (6, Phase.FLOP, Position.BUTTON,
         [Position.SB, Position.BB, Position.UTG, Position.HJ, Position.CO, Position.BUTTON]),
        
        # 10-max scenarios
        (10, Phase.PREFLOP, Position.BUTTON,
         [Position.UTG, Position.UTG1, Position.UTG2, Position.MP, Position.LJ, Position.HJ, Position.CO, Position.BUTTON, Position.SB, Position.BB]),
        (10, Phase.FLOP, Position.BUTTON,
         [Position.SB, Position.BB, Position.UTG, Position.UTG1, Position.UTG2, Position.MP, Position.LJ, Position.HJ, Position.CO, Position.BUTTON]),
    ])
    def test_betting_order_shapes(self, num_players, phase, button, expected):
        """Test that betting order shapes are correct for all scenarios."""
        got = BettingOrder.get_betting_order(num_players, phase, button)
        assert got == expected, f"Player count {num_players}, {phase}: expected {expected}, got {got}"

    def test_heads_up_special_cases(self):
        """Explicitly test heads-up quirks to prevent regression."""
        # Preflop: SB acts first, BB acts last
        preflop_order = BettingOrder.get_betting_order(2, Phase.PREFLOP)
        assert preflop_order == [Position.SB, Position.BB]
        
        # Postflop: BB acts first (left of button), SB (button) acts last
        postflop_order = BettingOrder.get_betting_order(2, Phase.FLOP)
        assert postflop_order == [Position.BB, Position.SB]

    def test_postflop_consistency(self):
        """Test that all postflop phases use the same order."""
        for player_count in [3, 4, 5, 6, 7, 8, 9, 10]:
            flop = BettingOrder.get_betting_order(player_count, Phase.FLOP)
            turn = BettingOrder.get_betting_order(player_count, Phase.TURN)
            river = BettingOrder.get_betting_order(player_count, Phase.RIVER)
            
            assert flop == turn == river, f"Player count {player_count}: postflop phases should be identical"

    def test_invalid_player_counts(self):
        """Test that invalid player counts raise appropriate errors."""
        with pytest.raises(ValueError, match="Unsupported player count: 1"):
            BettingOrder.get_betting_order(1, Phase.PREFLOP)
        
        with pytest.raises(ValueError, match="Unsupported player count: 11"):
            BettingOrder.get_betting_order(11, Phase.PREFLOP)

    def test_button_parameter_ignored(self):
        """Test that button parameter is ignored in position-relative approach."""
        # Should get same result regardless of button position
        order1 = BettingOrder.get_betting_order(6, Phase.PREFLOP, Position.BUTTON)
        order2 = BettingOrder.get_betting_order(6, Phase.PREFLOP, Position.SB)
        order3 = BettingOrder.get_betting_order(6, Phase.PREFLOP, None)
        
        assert order1 == order2 == order3, "Button parameter should not affect result in position-relative approach"