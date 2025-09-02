"""
Pot manager for centralized chip movements and side-pot construction.

This module handles all pot-related operations including:
- Tracking player contributions
- Building side pots for all-in scenarios
- Managing pot eligibility
"""

import pytest

from quads.engine.pot_manager import PotManager

PlayerId = int


class TestPotManager:
    """Test the pot manager functionality."""
    
    def test_basic_three_player_pot(self):
        """Test basic scenario: three players contribute equally."""
        players = {1, 2, 3}
        pm = PotManager(players)
        
        # All players contribute 100 cents
        pm.post(1, 100)
        pm.post(2, 100)
        pm.post(3, 100)
        
        pots = pm.build_pots()
        
        # Should be one pot with 300 cents, all players eligible
        assert len(pots) == 1
        assert pots[0].amount_cents == 300
        assert pots[0].eligible == {1, 2, 3}
        assert pm.total_table_cents() == 300
    
    def test_one_short_stack(self):
        """Test scenario with one short stack."""
        players = {1, 2, 3}
        pm = PotManager(players)
        
        # Player 1 contributes 100, others contribute 300
        pm.post(1, 100)
        pm.post(2, 300)
        pm.post(3, 300)
        
        pots = pm.build_pots()
        
        # Should be two pots:
        # 1. 300 cents (100 * 3 players) - all eligible
        # 2. 400 cents (200 * 2 players) - only players 2,3 eligible
        assert len(pots) == 2
        
        # First pot: 100 * 3 = 300, all eligible
        assert pots[0].amount_cents == 300
        assert pots[0].eligible == {1, 2, 3}
        
        # Second pot: 200 * 2 = 400, only 2,3 eligible
        assert pots[1].amount_cents == 400
        assert pots[1].eligible == {2, 3}
        
        assert pm.total_table_cents() == 700
    
    def test_two_all_ins_plus_fold(self):
        """Test complex scenario with all-ins and folds."""
        players = {1, 2, 3, 4}
        pm = PotManager(players)
        
        # Player 1: all-in with 100
        pm.post(1, 100)
        
        # Player 2: all-in with 250
        pm.post(2, 250)
        
        # Player 3: contributes 400
        pm.post(3, 400)
        
        # Player 4: contributes 400 then folds
        pm.post(4, 400)
        pm.mark_folded(4)
        
        pots = pm.build_pots()
        
        # Should be three pots:
        # 1. 400 cents (100 * 4 players) - all eligible except 4
        # 2. 450 cents (150 * 3 players) - 2,3 eligible (1 can't win more)
        # 3. 300 cents (150 * 2 players) - only 3 eligible (2 can't win more)
        assert len(pots) == 3
        
        # First pot: 100 * 4 = 400, all except 4 eligible
        assert pots[0].amount_cents == 400
        assert pots[0].eligible == {1, 2, 3}
        
        # Second pot: 150 * 3 = 450, 2,3 eligible
        assert pots[1].amount_cents == 450
        assert pots[1].eligible == {2, 3}
        
        # Third pot: 150 * 2 = 300, only 3 eligible
        assert pots[2].amount_cents == 300
        assert pots[2].eligible == {3}
        
        assert pm.total_table_cents() == 1150
    
    def test_invariant_sum_equals_total(self):
        """Test that sum of pot amounts equals total contributions."""
        players = {1, 2, 3, 4}
        pm = PotManager(players)
        
        # Complex scenario
        pm.post(1, 50)
        pm.post(2, 150)
        pm.post(3, 300)
        pm.post(4, 300)
        pm.mark_folded(2)
        
        pots = pm.build_pots()
        
        # Verify invariant: sum(pot amounts) == sum(contributions)
        pot_sum = sum(pot.amount_cents for pot in pots)
        contrib_sum = pm.total_table_cents()
        
        assert pot_sum == contrib_sum
        assert pot_sum == 800  # 50 + 150 + 300 + 300
    
    def test_empty_pot(self):
        """Test empty pot scenario."""
        players = {1, 2, 3}
        pm = PotManager(players)
        
        pots = pm.build_pots()
        
        assert len(pots) == 0
        assert pm.total_table_cents() == 0
    
    def test_single_player_pot(self):
        """Test pot with only one player contributing."""
        players = {1, 2, 3}
        pm = PotManager(players)
        
        pm.post(1, 100)
        
        pots = pm.build_pots()
        
        assert len(pots) == 1
        assert pots[0].amount_cents == 100
        assert pots[0].eligible == {1}
        assert pm.total_table_cents() == 100
    
    def test_all_players_folded(self):
        """Test scenario where all players fold."""
        players = {1, 2, 3}
        pm = PotManager(players)
        
        pm.post(1, 100)
        pm.post(2, 100)
        pm.post(3, 100)
        pm.mark_folded(1)
        pm.mark_folded(2)
        pm.mark_folded(3)
        
        pots = pm.build_pots()
        
        # Should still have one pot, but no eligible players
        assert len(pots) == 1
        assert pots[0].amount_cents == 300
        assert pots[0].eligible == set()
        assert pm.total_table_cents() == 300
    
    def test_player_contribution_tracking(self):
        """Test individual player contribution tracking."""
        players = {1, 2}
        pm = PotManager(players)
        
        pm.post(1, 100)
        pm.post(2, 200)
        
        assert pm.get_player_contribution(1) == 100
        assert pm.get_player_contribution(2) == 200
    
    def test_fold_tracking(self):
        """Test fold status tracking."""
        players = {1, 2}
        pm = PotManager(players)
        
        assert not pm.is_player_folded(1)
        assert not pm.is_player_folded(2)
        
        pm.mark_folded(1)
        
        assert pm.is_player_folded(1)
        assert not pm.is_player_folded(2)
    
    def test_invalid_player_operations(self):
        """Test error handling for invalid player operations."""
        players = {1, 2}
        pm = PotManager(players)
        
        # Try to post for non-existent player
        with pytest.raises(ValueError, match="Player 3 not in pot manager"):
            pm.post(3, 100)
        
        # Try to mark non-existent player as folded
        with pytest.raises(ValueError, match="Player 3 not in pot manager"):
            pm.mark_folded(3)
        
        # Try to get contribution for non-existent player
        with pytest.raises(ValueError, match="Player 3 not in pot manager"):
            pm.get_player_contribution(3)
    
    def test_negative_contribution_rejected(self):
        """Test that negative contributions are rejected."""
        players = {1}
        pm = PotManager(players)
        
        # This should raise ValueError from nonneg()
        with pytest.raises(ValueError, match="Negative amount not allowed"):
            pm.post(1, -50)
    
    def test_multiple_contributions_same_player(self):
        """Test multiple contributions from the same player."""
        players = {1, 2}
        pm = PotManager(players)
        
        pm.post(1, 100)
        pm.post(1, 50)  # Additional contribution
        pm.post(2, 200)
        
        assert pm.get_player_contribution(1) == 150
        assert pm.get_player_contribution(2) == 200
        
        pots = pm.build_pots()
        
        # Should be two pots:
        # 1. 300 cents (150 * 2 players) - both eligible
        # 2. 50 cents (50 * 1 player) - only player 2 eligible
        assert len(pots) == 2
        assert pots[0].amount_cents == 300
        assert pots[0].eligible == {1, 2}
        assert pots[1].amount_cents == 50
        assert pots[1].eligible == {2}
        
        assert pm.total_table_cents() == 350
    
    def test_pot_immutability(self):
        """Test that Pot objects are immutable."""
        players = {1}
        pm = PotManager(players)
        pm.post(1, 100)
        
        pots = pm.build_pots()
        pot = pots[0]
        
        # Verify pot is immutable
        assert pot.amount_cents == 100
        assert pot.eligible == {1}
        
        # Should not be able to modify frozen dataclass
        with pytest.raises(Exception):  # Frozen dataclass raises on modification
            pot.amount_cents = 200 