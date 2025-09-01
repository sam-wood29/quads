"""
Payout resolution for exact chip distribution.

This module handles the distribution of chips from pots to winners,
ensuring no cents are lost and ties are handled correctly.
"""

from typing import Dict, List, Set, Iterable, Tuple

from .money import Cents
from .pot_manager import Pot


def resolve_payouts(
    pots: List[Pot],
    ranks: Dict[int, int],           # player_id -> rank (1,2,3...) among remaining
    seat_order: List[int],           # stable tie-break for $0.01 remainders
) -> Dict[int, Cents]:               # player_id -> won_cents
    """
    Resolve payouts from pots based on showdown ranks.
    
    Args:
        pots: List of pots with amounts and eligible players
        ranks: Dict mapping player_id to rank (lower is better, 1 = best)
        seat_order: List of player IDs in seat order for stable tie-breaking
        
    Returns:
        Dict mapping player_id to won_cents
        
    Notes:
        - Ties share equally
        - Any 1-cent remainders go to earliest seat index (stable rule)
        - No cents are lost in the distribution
    """
    payouts: Dict[int, Cents] = {pid: 0 for pid in ranks}
    
    for pot in pots:
        # Find players eligible for this pot who also have ranks
        contenders = [p for p in pot.eligible if p in ranks]
        
        # Skip empty pots or pots with no eligible contenders
        if not contenders or pot.amount_cents <= 0:
            continue
        
        # Find the best (lowest) rank among contenders
        best_rank = min(ranks[p] for p in contenders)
        
        # Find all players with the best rank
        winners = [p for p in contenders if ranks[p] == best_rank]
        
        # Calculate equal share and remainder
        share = pot.amount_cents // len(winners)
        remainder = pot.amount_cents % len(winners)
        
        # Sort winners by seat order for stable remainder distribution
        winners_sorted = sorted(winners, key=lambda pid: seat_order.index(pid))
        
        # Distribute shares and remainder
        for i, pid in enumerate(winners_sorted):
            # Each winner gets share + 1 cent if they're in the first 'remainder' positions
            payouts[pid] += share + (1 if i < remainder else 0)
    
    return payouts


def validate_payouts(
    pots: List[Pot],
    payouts: Dict[int, Cents],
    ranks: Dict[int, int],
) -> bool:
    """
    Validate that payouts are correct.
    
    Args:
        pots: List of pots
        payouts: Dict of player_id -> won_cents
        ranks: Dict of player_id -> rank
        
    Returns:
        True if payouts are valid, False otherwise
    """
    # Check that total payouts equals total pot amounts
    total_pot_amount = sum(pot.amount_cents for pot in pots)
    total_payouts = sum(payouts.values())
    
    if total_payouts != total_pot_amount:
        return False
    
    # Check that only players with ranks received payouts
    for pid in payouts:
        if pid not in ranks:
            return False
    
    # Check that payouts are non-negative
    for amount in payouts.values():
        if amount < 0:
            return False
    
    return True


def get_pot_winners(
    pot: Pot,
    ranks: Dict[int, int],
) -> List[int]:
    """
    Get the winners of a specific pot.
    
    Args:
        pot: The pot to evaluate
        ranks: Dict mapping player_id to rank
        
    Returns:
        List of player IDs who win this pot
    """
    contenders = [p for p in pot.eligible if p in ranks]
    
    if not contenders:
        return []
    
    best_rank = min(ranks[p] for p in contenders)
    winners = [p for p in contenders if ranks[p] == best_rank]
    
    return winners


def calculate_pot_share(
    pot_amount: Cents,
    num_winners: int,
) -> Tuple[Cents, Cents]:
    """
    Calculate equal share and remainder for a pot.
    
    Args:
        pot_amount: Total amount in the pot
        num_winners: Number of winners to split between
        
    Returns:
        Tuple of (equal_share, remainder)
    """
    if num_winners <= 0:
        return 0, pot_amount
    
    share = pot_amount // num_winners
    remainder = pot_amount % num_winners
    
    return share, remainder 