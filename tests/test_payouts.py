"""
Payout resolution for exact chip distribution.

This module handles the distribution of chips from pots to winners,
ensuring no cents are lost and ties are handled correctly.
"""

from typing import Dict, List, Set, Iterable, Tuple

from quads.engine.money import Cents
from quads.engine.pot_manager import Pot


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


import pytest

from quads.engine.money import Cents
from quads.engine.payouts import resolve_payouts, validate_payouts, get_pot_winners, calculate_pot_share
from quads.engine.pot_manager import Pot


class TestPayouts:
    """Test payout resolution functionality."""
    
    def test_single_pot_single_winner(self):
        """Test single pot with single winner."""
        # Create a single pot with 1000 cents, player 1 eligible
        pots = [Pot(amount_cents=1000, eligible={1})]
        
        # Player 1 has rank 1 (best)
        ranks = {1: 1}
        
        # Seat order for tie-breaking
        seat_order = [1]
        
        payouts = resolve_payouts(pots, ranks, seat_order)
        
        # Player 1 should get all 1000 cents
        assert payouts[1] == 1000
        assert len(payouts) == 1
        
        # Validate payouts
        assert validate_payouts(pots, payouts, ranks)
    
    def test_single_pot_two_way_tie_odd_remainder(self):
        """Test single pot with 2-way tie and odd cents remainder."""
        # Create a single pot with 1001 cents, players 1 and 2 eligible
        pots = [Pot(amount_cents=1001, eligible={1, 2})]
        
        # Both players have rank 1 (tie)
        ranks = {1: 1, 2: 1}
        
        # Seat order: player 1 first, then player 2
        seat_order = [1, 2]
        
        payouts = resolve_payouts(pots, ranks, seat_order)
        
        # Each should get 500 cents, player 1 gets the extra 1 cent
        assert payouts[1] == 501  # 500 + 1 (remainder)
        assert payouts[2] == 500
        assert len(payouts) == 2
        
        # Validate payouts
        assert validate_payouts(pots, payouts, ranks)
    
    def test_multi_pot_disjoint_eligibilities(self):
        """Test multi-pot with disjoint eligibilities (classic side-pot example)."""
        # Create side pots scenario:
        # Pot 1: 300 cents, players 1, 2, 3 eligible (main pot)
        # Pot 2: 200 cents, players 2, 3 eligible (side pot)
        # Pot 3: 100 cents, only player 3 eligible (side pot)
        pots = [
            Pot(amount_cents=300, eligible={1, 2, 3}),
            Pot(amount_cents=200, eligible={2, 3}),
            Pot(amount_cents=100, eligible={3})
        ]
        
        # Ranks: player 1 is best, player 2 is second, player 3 is worst
        ranks = {1: 1, 2: 2, 3: 3}
        
        # Seat order
        seat_order = [1, 2, 3]
        
        payouts = resolve_payouts(pots, ranks, seat_order)
        
        # Expected payouts:
        # Player 1: wins pot 1 (300 cents)
        # Player 2: wins pot 2 (200 cents)
        # Player 3: wins pot 3 (100 cents)
        assert payouts[1] == 300
        assert payouts[2] == 200
        assert payouts[3] == 100
        assert len(payouts) == 3
        
        # Validate payouts
        assert validate_payouts(pots, payouts, ranks)
    
    def test_multi_way_two_all_ins_scenario(self):
        """Test multi-way two-all-ins scenario (acceptance test)."""
        # Scenario: 4 players, 2 all-ins
        # Player 1: all-in with 100 cents
        # Player 2: all-in with 250 cents
        # Player 3: calls with 400 cents
        # Player 4: calls with 400 cents
        
        # This creates 3 pots:
        # Pot 1: 400 cents (100 * 4 players) - all eligible
        # Pot 2: 450 cents (150 * 3 players) - players 2, 3, 4 eligible
        # Pot 3: 300 cents (150 * 2 players) - players 3, 4 eligible
        pots = [
            Pot(amount_cents=400, eligible={1, 2, 3, 4}),
            Pot(amount_cents=450, eligible={2, 3, 4}),
            Pot(amount_cents=300, eligible={3, 4})
        ]
        
        # Ranks: player 3 wins, player 4 second, others eliminated
        ranks = {3: 1, 4: 2}
        
        # Seat order
        seat_order = [1, 2, 3, 4]
        
        payouts = resolve_payouts(pots, ranks, seat_order)
        
        # Expected payouts:
        # Player 3: wins all pots (400 + 450 + 300 = 1150 cents)
        # Player 4: gets nothing (eliminated)
        # Players 1, 2: get nothing (eliminated)
        assert payouts[3] == 1150
        assert payouts[4] == 0
        assert len(payouts) == 2
        
        # Validate total equals table amount
        total_payouts = sum(payouts.values())
        total_pot_amount = sum(pot.amount_cents for pot in pots)
        assert total_payouts == total_pot_amount
        assert total_payouts == 1150
        
        # Validate payouts
        assert validate_payouts(pots, payouts, ranks)
    
    def test_empty_pots(self):
        """Test handling of empty pots."""
        pots = []
        ranks = {1: 1}
        seat_order = [1]
        
        payouts = resolve_payouts(pots, ranks, seat_order)
        
        assert payouts[1] == 0
        assert validate_payouts(pots, payouts, ranks)
    
    def test_zero_amount_pot(self):
        """Test handling of zero amount pot."""
        pots = [Pot(amount_cents=0, eligible={1, 2})]
        ranks = {1: 1, 2: 2}
        seat_order = [1, 2]
        
        payouts = resolve_payouts(pots, ranks, seat_order)
        
        assert payouts[1] == 0
        assert payouts[2] == 0
        assert validate_payouts(pots, payouts, ranks)
    
    def test_no_eligible_contenders(self):
        """Test pot with no eligible contenders."""
        """Testing an edge case that should never exist in a properly
           designed system"""
        pots = [Pot(amount_cents=1000, eligible={1, 2})]
        ranks = {3: 1}  # Only player 3 has rank, but not eligible for pot
        print("pots")
        print(pots)
        print("ranks")
        print(ranks)
        
        seat_order = [1, 2, 3]
        
        payouts = resolve_payouts(pots, ranks, seat_order)
        print("payouts")
        print(payouts)
        print("\n\n")
        
        assert payouts[3] == 0
        assert not validate_payouts(pots, payouts, ranks)
    
    def test_three_way_tie_with_remainder(self):
        """Test three-way tie with remainder distribution."""
        pots = [Pot(amount_cents=1001, eligible={1, 2, 3})]
        ranks = {1: 1, 2: 1, 3: 1}  # All tie
        seat_order = [1, 2, 3]
        
        payouts = resolve_payouts(pots, ranks, seat_order)
        print(payouts)
        
        
        assert payouts[1] == 334
        assert payouts[2] == 334
        assert payouts[3] == 333
        assert sum(payouts.values()) == 1001
        
        assert validate_payouts(pots, payouts, ranks)
    
    def test_complex_side_pot_scenario(self):
        """Test complex side pot scenario with multiple all-ins."""
        # Scenario with 5 players:
        # Player 1: all-in 50 cents
        # Player 2: all-in 100 cents
        # Player 3: all-in 200 cents
        # Player 4: calls 300 cents
        # Player 5: calls 300 cents
        
        # Creates 4 pots:
        # Pot 1: 250 cents (50 * 5) - all eligible
        # Pot 2: 200 cents (50 * 4) - players 2, 3, 4, 5 eligible
        # Pot 3: 300 cents (100 * 3) - players 3, 4, 5 eligible
        # Pot 4: 200 cents (100 * 2) - players 4, 5 eligible
        pots = [
            Pot(amount_cents=250, eligible={1, 2, 3, 4, 5}),
            Pot(amount_cents=200, eligible={2, 3, 4, 5}),
            Pot(amount_cents=300, eligible={3, 4, 5}),
            Pot(amount_cents=200, eligible={4, 5})
        ]
        
        # Ranks: player 4 wins, player 5 second, others eliminated
        ranks = {4: 1, 5: 2}
        
        seat_order = [1, 2, 3, 4, 5]
        
        payouts = resolve_payouts(pots, ranks, seat_order)
        
        # Expected payouts:
        # Player 4: wins all pots (250 + 200 + 300 + 200 = 950 cents)
        # Player 5: gets nothing (eliminated)
        assert payouts[4] == 950
        assert payouts[5] == 0
        
        # Validate total
        total_payouts = sum(payouts.values())
        total_pot_amount = sum(pot.amount_cents for pot in pots)
        assert total_payouts == total_pot_amount
        assert total_payouts == 950
        
        assert validate_payouts(pots, payouts, ranks)
    
    def test_seat_order_stability(self):
        """Test that seat order provides stable tie-breaking."""
        pots = [Pot(amount_cents=1001, eligible={1, 2})]
        ranks = {1: 1, 2: 1}  # Tie
        
        # Test with different seat orders
        seat_order_1 = [1, 2]  # Player 1 first
        seat_order_2 = [2, 1]  # Player 2 first
        
        payouts_1 = resolve_payouts(pots, ranks, seat_order_1)
        payouts_2 = resolve_payouts(pots, ranks, seat_order_2)
        
        # Player 1 should get extra cent when first in seat order
        assert payouts_1[1] == 501
        assert payouts_1[2] == 500
        
        # Player 2 should get extra cent when first in seat order
        assert payouts_2[1] == 500
        assert payouts_2[2] == 501
        
        # Both should be valid
        assert validate_payouts(pots, payouts_1, ranks)
        assert validate_payouts(pots, payouts_2, ranks)
    
    def test_get_pot_winners(self):
        """Test get_pot_winners helper function."""
        from quads.engine.payouts import get_pot_winners
        
        pot = Pot(amount_cents=1000, eligible={1, 2, 3})
        ranks = {1: 1, 2: 1, 3: 2}  # Players 1 and 2 tie for best
        
        winners = get_pot_winners(pot, ranks)
        
        assert set(winners) == {1, 2}
        assert 3 not in winners
    
    def test_calculate_pot_share(self):
        """Test calculate_pot_share helper function."""
        from quads.engine.payouts import calculate_pot_share
        
        # Test even division
        share, remainder = calculate_pot_share(1000, 2)
        assert share == 500
        assert remainder == 0
        
        # Test odd division
        share, remainder = calculate_pot_share(1001, 2)
        assert share == 500
        assert remainder == 1
        
        # Test zero winners
        share, remainder = calculate_pot_share(1000, 0)
        assert share == 0
        assert remainder == 1000
    
    def test_validation_failures(self):
        """Test validation failure cases."""
        pots = [Pot(amount_cents=1000, eligible={1})]
        ranks = {1: 1}
        
        # Valid payouts
        valid_payouts = {1: 1000}
        assert validate_payouts(pots, valid_payouts, ranks)
        
        # Invalid: wrong total
        invalid_payouts_1 = {1: 999}
        assert not validate_payouts(pots, invalid_payouts_1, ranks)
        
        # Invalid: negative payout
        invalid_payouts_2 = {1: -1}
        assert not validate_payouts(pots, invalid_payouts_2, ranks)
        
        # Invalid: player not in ranks
        invalid_payouts_3 = {2: 1000}
        assert not validate_payouts(pots, invalid_payouts_3, ranks) 