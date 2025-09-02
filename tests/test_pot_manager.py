"""
Pot manager for centralized chip movements and side-pot construction.

This module handles all pot-related operations including:
- Tracking player contributions
- Building side pots for all-in scenarios
- Managing pot eligibility
"""

from dataclasses import dataclass

from quads.engine.money import Cents, nonneg

PlayerId = int


@dataclass(frozen=True)
class Pot:
    """Represents a pot with amount and eligible players."""
    amount_cents: Cents
    eligible: set[PlayerId]  # players who can win from this pot


class PotManager:
    """
    Manages pot construction and chip movements.
    
    Tracks player contributions and builds side pots for all-in scenarios.
    Keeps betting logic simpler by centralizing pot operations.
    """
    
    def __init__(self, players: set[PlayerId]):
        """
        Initialize pot manager with set of player IDs.
        
        Args:
            players: Set of player IDs participating in the hand
        """
        self.contributed: dict[PlayerId, Cents] = {pid: 0 for pid in players}
        self.folded: set[PlayerId] = set()
    
    def post(self, pid: PlayerId, cents: Cents) -> None:
        """
        Move chips from player to table (caller handles stack decrement).
        
        Args:
            pid: Player ID making the contribution
            cents: Amount to contribute in cents
        """
        if pid not in self.contributed:
            raise ValueError(f"Player {pid} not in pot manager")
        
        self.contributed[pid] = nonneg(self.contributed[pid] + cents)
    
    def mark_folded(self, pid: PlayerId) -> None:
        """
        Mark a player as folded (ineligible for pots).
        
        Args:
            pid: Player ID who folded
        """
        if pid not in self.contributed:
            raise ValueError(f"Player {pid} not in pot manager")
        
        self.folded.add(pid)
    
    def build_pots(self) -> list[Pot]:
        """
        Build side pots by contribution tiers.
        
        Side-pot construction by tiers:
        - L = sorted unique contribution levels (>0) among all players
        - For tier i with height Δ = L[i] - L[i-1], size = Δ * (#contributors ≥ L[i])
        - eligible = players with contributed ≥ L[i] and not folded
        
        Returns:
            List of pots with amounts and eligible players
        """
        contrib = self.contributed
        
        # Get sorted unique contribution levels (>0)
        levels = sorted({v for v in contrib.values() if v > 0})
        if not levels:
            return []
        
        pots: list[Pot] = []
        prev = 0
        
        for L in levels:
            delta = L - prev
            
            # Players contributing at this level or higher
            tier_players = {p for p, v in contrib.items() if v >= L}
            
            # Pot amount = delta * number of players at this tier
            amount = delta * len(tier_players)
            
            # Eligible players = tier players who haven't folded
            eligible = {p for p in tier_players if p not in self.folded}
            
            if amount > 0:
                pots.append(Pot(amount_cents=amount, eligible=eligible))
            
            prev = L
        
        return pots
    
    def total_table_cents(self) -> Cents:
        """
        Get total amount on the table.
        
        Returns:
            Sum of all player contributions
        """
        return sum(self.contributed.values())
    
    def get_player_contribution(self, pid: PlayerId) -> Cents:
        """
        Get a player's total contribution.
        
        Args:
            pid: Player ID
            
        Returns:
            Player's contribution in cents
        """
        if pid not in self.contributed:
            raise ValueError(f"Player {pid} not in pot manager")
        
        return self.contributed[pid]
    
    def is_player_folded(self, pid: PlayerId) -> bool:
        """
        Check if a player has folded.
        
        Args:
            pid: Player ID
            
        Returns:
            True if player has folded
        """
        return pid in self.folded

import pytest

from quads.engine.money import Cents
from quads.engine.pot_manager import Pot, PotManager


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