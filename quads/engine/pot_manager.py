"""
Pot manager for centralized chip movements and side-pot construction.

This module handles all pot-related operations including:
- Tracking player contributions
- Building side pots for all-in scenarios
- Managing pot eligibility
"""

from dataclasses import dataclass

from .money import Cents, nonneg

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
    
    def __str__(self) -> str:
        """Comprehensive string representation for debugging."""
        # Convert cents to dollars for display
        total_cents = self.total_table_cents()
        total_dollars = total_cents / 100.0
        
        # Format contributions
        contrib_strs = []
        for pid in sorted(self.contributed.keys()):
            contrib_cents = self.contributed[pid]
            contrib_dollars = contrib_cents / 100.0
            status = "FOLDED" if pid in self.folded else "ACTIVE"
            contrib_strs.append(f"P{pid}: ${contrib_dollars:.2f} ({status})")
        
        # Format folded players
        folded_str = f"Folded: {sorted(self.folded)}" if self.folded else "Folded: None"
        
        # Build pots for display
        pots = self.build_pots()
        pot_strs = []
        for i, pot in enumerate(pots):
            pot_dollars = pot.amount_cents / 100.0
            eligible_str = ",".join(f"P{pid}" for pid in sorted(pot.eligible))
            pot_strs.append(f"Pot{i+1}: ${pot_dollars:.2f} [eligible: {eligible_str}]")
        
        pots_str = "\n    ".join(pot_strs) if pot_strs else "No pots built"
        
        return (f"PotManager(total=${total_dollars:.2f}, "
                f"contributions=[{', '.join(contrib_strs)}], "
                f"{folded_str})\n"
                f"    Built pots:\n    {pots_str}")
    
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