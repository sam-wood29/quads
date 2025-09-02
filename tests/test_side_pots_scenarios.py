
from quads.engine.payouts import resolve_payouts, validate_payouts
from quads.engine.pot_manager import PotManager


class TestSidePotScenarios:
    """Test side-pot construction and payout resolution scenarios."""
    
    def test_canonical_two_all_ins_scenario_c_wins(self):
        """Test the canonical two all-ins + caller scenario with C winning overall."""
        # Setup: A=600, B=300, C=1200
        # Action: B all-in 300, C re-raises all-in 1200, A calls 600
        contributions = {1: 600, 2: 300, 3: 1200}  # A, B, C
        pm = PotManager(set(contributions.keys()))
        
        # Post contributions
        for pid, amount in contributions.items():
            pm.post(pid, amount)
        
        # Build pots
        pots = pm.build_pots()
        
        # Expected pots based on contribution tiers:
        # Tier 1: 300 (all contribute at least 300)
        # Tier 2: 600 (A and C contribute at least 600) 
        # Tier 3: 1200 (only C contributes 1200)
        assert len(pots) == 3
        
        # Main pot: 300 × 3 = 900, all eligible
        assert pots[0].amount_cents == 900
        assert pots[0].eligible == {1, 2, 3}
        
        # Side pot 1: 300 × 2 = 600, A,C eligible (B can't win more)
        assert pots[1].amount_cents == 600
        assert pots[1].eligible == {1, 3}
        
        # Side pot 2: 600 × 1 = 600, only C eligible
        assert pots[2].amount_cents == 600
        assert pots[2].eligible == {3}
        
        # Test payout resolution: C wins overall
        ranks = {1: 2, 2: 3, 3: 1}  # A=2nd, B=3rd, C=1st
        seat_order = [1, 2, 3]
        
        payouts = resolve_payouts(pots, ranks, seat_order)
        
        # Expected payouts:
        # C wins all pots: 900 + 600 + 600 = 2100
        # A gets nothing (eliminated)
        # B gets nothing (eliminated)
        assert payouts[1] == 0  # A
        assert payouts[2] == 0  # B
        assert payouts[3] == 2100  # C
        
        # Verify invariants
        assert sum(pot.amount_cents for pot in pots) == sum(contributions.values())
        assert sum(payouts.values()) == sum(contributions.values())
        assert validate_payouts(pots, payouts, ranks)
    
    def test_canonical_two_all_ins_scenario_a_beats_b(self):
        """Test the canonical scenario with A beating B, C winning overall."""
        # Same setup as above
        contributions = {1: 600, 2: 300, 3: 1200}
        pm = PotManager(set(contributions.keys()))
        
        for pid, amount in contributions.items():
            pm.post(pid, amount)
        
        pots = pm.build_pots()
        
        # Test payout resolution: A beats B, C wins overall
        ranks = {1: 1, 2: 2, 3: 3}  # A=1st, B=2nd, C=3rd
        seat_order = [1, 2, 3]
        
        payouts = resolve_payouts(pots, ranks, seat_order)
        
        # Expected payouts:
        # Main pot (900): A wins (900)
        # Side pot 1 (600): A wins (600)
        # Side pot 2 (600): C wins (600)
        assert payouts[1] == 1500  # A: 900 + 600
        assert payouts[2] == 0     # B: nothing
        assert payouts[3] == 600   # C: 600
        
        # Verify invariants
        assert sum(payouts.values()) == sum(contributions.values())
        assert validate_payouts(pots, payouts, ranks)
    
    def test_two_all_ins_with_folder(self):
        """Test scenario with two all-ins and one folder."""
        # Setup: A=600, B=300, C=1200, D=600 (then folds)
        contributions = {1: 600, 2: 300, 3: 1200, 4: 600}
        pm = PotManager(set(contributions.keys()))
        
        # Post contributions
        for pid, amount in contributions.items():
            pm.post(pid, amount)
        
        # D folds
        pm.mark_folded(4)
        
        # Build pots
        pots = pm.build_pots()
        
        # Expected pots based on contribution tiers:
        # Tier 1: 300 (all contribute at least 300)
        # Tier 2: 600 (A, C, D contribute at least 600) - but D folded
        # Tier 3: 1200 (only C contributes 1200)
        assert len(pots) == 3
        
        # Main pot: 300 × 4 = 1200, A,B,C eligible (D folded)
        assert pots[0].amount_cents == 1200
        assert pots[0].eligible == {1, 2, 3}
        
        # Side pot 1: 300 × 3 = 900, A,C eligible (D folded, B can't win more)
        assert pots[1].amount_cents == 900
        assert pots[1].eligible == {1, 3}
        
        # Side pot 2: 600 × 1 = 600, only C eligible
        assert pots[2].amount_cents == 600
        assert pots[2].eligible == {3}
        
        # Test payout resolution: C wins overall
        # Note: D is not in ranks because they folded
        ranks = {1: 2, 2: 3, 3: 1}  # A=2nd, B=3rd, C=1st
        seat_order = [1, 2, 3, 4]
        
        payouts = resolve_payouts(pots, ranks, seat_order)
        
        # Expected payouts:
        # C wins all pots: 1200 + 900 + 600 = 2700
        # A gets nothing (eliminated)
        # B gets nothing (eliminated)
        # D gets nothing (folded) - but D is not in payouts because they have no rank
        assert payouts[1] == 0  # A
        assert payouts[2] == 0  # B
        assert payouts[3] == 2700  # C
        # Don't check payouts[4] because D is not in ranks
        
        # Verify invariants
        assert sum(pot.amount_cents for pot in pots) == sum(contributions.values())
        assert sum(payouts.values()) == sum(contributions.values())
        assert validate_payouts(pots, payouts, ranks)
    
    def test_remainder_pennies_distribution(self):
        """Test stable remainder distribution for ties."""
        # Setup: Two players contribute equally and tie
        contributions = {1: 100, 2: 100}  # Both contribute 100
        pm = PotManager(set(contributions.keys()))
        
        for pid, amount in contributions.items():
            pm.post(pid, amount)
        
        pots = pm.build_pots()
        assert len(pots) == 1
        assert pots[0].amount_cents == 200  # 100 × 2
        assert pots[0].eligible == {1, 2}
        
        # Two players tie for the pot
        ranks = {1: 1, 2: 1}  # Both tie for 1st
        seat_order = [1, 2]
        
        payouts = resolve_payouts(pots, ranks, seat_order)
        
        # Expected: Each gets 100 cents (200 / 2)
        assert payouts[1] == 100
        assert payouts[2] == 100
        
        # Verify total
        assert sum(payouts.values()) == 200
    
    def test_remainder_pennies_with_odd_amount(self):
        """Test remainder distribution with odd amount."""
        # Setup: 101 cent pot, two winners tie
        contributions = {1: 51, 2: 50}  # Total 101
        pm = PotManager(set(contributions.keys()))
        
        for pid, amount in contributions.items():
            pm.post(pid, amount)
        
        pots = pm.build_pots()
        
        # Two players tie for the pot
        ranks = {1: 1, 2: 1}  # Tie
        seat_order = [1, 2]
        
        payouts = resolve_payouts(pots, ranks, seat_order)
        
        # Expected: Each gets 50 cents, remainder 1 goes to earliest seat (1)
        assert payouts[1] == 51  # 50 + 1 (remainder)
        assert payouts[2] == 50  # 50 + 0
        
        # Verify total
        assert sum(payouts.values()) == 101
    
    def test_three_way_tie_with_remainder(self):
        """Test three-way tie with remainder distribution."""
        # Setup: Three players contribute equally
        contributions = {1: 100, 2: 100, 3: 100}  # Total 300
        pm = PotManager(set(contributions.keys()))
        
        for pid, amount in contributions.items():
            pm.post(pid, amount)
        
        pots = pm.build_pots()
        
        # Three players tie for the pot
        ranks = {1: 1, 2: 1, 3: 1}  # All tie for 1st
        seat_order = [1, 2, 3]
        
        payouts = resolve_payouts(pots, ranks, seat_order)
        
        # Expected: Each gets 100 cents (300 / 3)
        assert payouts[1] == 100
        assert payouts[2] == 100
        assert payouts[3] == 100
        
        # Verify total
        assert sum(payouts.values()) == 300
    
    def test_three_way_tie_with_remainder_odd(self):
        """Test three-way tie with odd remainder."""
        # Setup: 1002 cent pot, three winners tie
        contributions = {1: 334, 2: 334, 3: 334}  # Total 1002
        pm = PotManager(set(contributions.keys()))
        
        for pid, amount in contributions.items():
            pm.post(pid, amount)
        
        pots = pm.build_pots()
        
        # Three players tie for the pot
        ranks = {1: 1, 2: 1, 3: 1}  # All tie for 1st
        seat_order = [1, 2, 3]
        
        payouts = resolve_payouts(pots, ranks, seat_order)
        
        # Expected: Each gets 334 cents, remainder 0
        assert payouts[1] == 334
        assert payouts[2] == 334
        assert payouts[3] == 334
        
        # Verify total
        assert sum(payouts.values()) == 1002
    
    def test_pot_construction_invariants(self):
        """Test that pot construction maintains invariants."""
        # Test various scenarios
        test_cases = [
            # Simple case
            {1: 100, 2: 100},
            # All-in scenario
            {1: 50, 2: 100, 3: 200},
            # Complex scenario
            {1: 25, 2: 50, 3: 100, 4: 200},
        ]
        
        for contributions in test_cases:
            pm = PotManager(set(contributions.keys()))
            
            for pid, amount in contributions.items():
                pm.post(pid, amount)
            
            pots = pm.build_pots()
            
            # Invariant: sum(pot amounts) == sum(contributions)
            total_pot_amount = sum(pot.amount_cents for pot in pots)
            total_contributions = sum(contributions.values())
            assert total_pot_amount == total_contributions, f"Failed for {contributions}"
            
            # Invariant: each pot has eligible players
            for pot in pots:
                assert len(pot.eligible) > 0, f"Empty eligible set for pot {pot}"
    
    def test_payout_resolution_invariants(self):
        """Test that payout resolution maintains invariants."""
        # Test various scenarios
        contributions = {1: 100, 2: 200, 3: 300}
        pm = PotManager(set(contributions.keys()))
        
        for pid, amount in contributions.items():
            pm.post(pid, amount)
        
        pots = pm.build_pots()
        
        # Test different rank scenarios
        rank_scenarios = [
            {1: 1, 2: 2, 3: 3},  # 1 wins
            {1: 2, 2: 1, 3: 3},  # 2 wins
            {1: 3, 2: 2, 3: 1},  # 3 wins
            {1: 1, 2: 1, 3: 2},  # 1,2 tie
        ]
        
        seat_order = [1, 2, 3]
        
        for ranks in rank_scenarios:
            payouts = resolve_payouts(pots, ranks, seat_order)
            
            # Invariant: sum(payouts) == sum(contributions)
            assert sum(payouts.values()) == sum(contributions.values())
            
            # Invariant: only players with ranks get payouts
            for pid in payouts:
                assert pid in ranks
            
            # Invariant: payouts are non-negative
            for amount in payouts.values():
                assert amount >= 0
            
            # Invariant: validation passes
            assert validate_payouts(pots, payouts, ranks)
    
    def test_eligibility_rules(self):
        """Test that eligibility rules are followed correctly."""
        # Setup: A=100, B=200, C=300, D=400
        contributions = {1: 100, 2: 200, 3: 300, 4: 400}
        pm = PotManager(set(contributions.keys()))
        
        for pid, amount in contributions.items():
            pm.post(pid, amount)
        
        # D folds
        pm.mark_folded(4)
        
        pots = pm.build_pots()
        
        # Should create 4 pots (one for each contribution tier)
        assert len(pots) == 4
        
        # Verify D is excluded from all pots
        for pot in pots:
            assert 4 not in pot.eligible, f"D should not be eligible for pot {pot}"
        
        # Verify other players are eligible based on contribution levels
        # Main pot (100 × 4): all eligible except D
        assert pots[0].amount_cents == 400  # 100 × 4
        assert pots[0].eligible == {1, 2, 3}
        
        # Side pot 1 (100 × 3): B,C eligible (A can't win more)
        assert pots[1].amount_cents == 300  # 100 × 3
        assert pots[1].eligible == {2, 3}
        
        # Side pot 2 (100 × 2): C eligible (B can't win more)
        assert pots[2].amount_cents == 200  # 100 × 2
        assert pots[2].eligible == {3}
        
        # Side pot 3 (100 × 1): no one eligible (D folded)
        assert pots[3].amount_cents == 100  # 100 × 1
        assert pots[3].eligible == set()  # Empty set - no one eligible
    
    def test_empty_pot_scenario(self):
        """Test handling of empty pot scenario."""
        # No contributions
        pm = PotManager({1, 2, 3})
        pots = pm.build_pots()
        
        assert len(pots) == 0
        assert pm.total_table_cents() == 0
        
        # Test payout resolution with empty pots
        ranks = {1: 1, 2: 2, 3: 3}
        seat_order = [1, 2, 3]
        
        payouts = resolve_payouts(pots, ranks, seat_order)
        
        assert payouts[1] == 0
        assert payouts[2] == 0
        assert payouts[3] == 0
        assert validate_payouts(pots, payouts, ranks)
    
    def test_all_players_folded_scenario(self):
        """Test scenario where all players fold."""
        # Setup: Everyone contributes then folds
        contributions = {1: 100, 2: 100, 3: 100}
        pm = PotManager(set(contributions.keys()))
        
        for pid, amount in contributions.items():
            pm.post(pid, amount)
            pm.mark_folded(pid)  # Everyone folds
        
        pots = pm.build_pots()
        
        # Should still have one pot, but no eligible players
        assert len(pots) == 1
        assert pots[0].amount_cents == 300
        assert pots[0].eligible == set()  # No one eligible
        
        # Test payout resolution
        ranks = {1: 1, 2: 2, 3: 3}  # Ranks don't matter since no one eligible
        seat_order = [1, 2, 3]
        
        payouts = resolve_payouts(pots, ranks, seat_order)
        
        # No one gets anything since no one is eligible
        assert payouts[1] == 0
        assert payouts[2] == 0
        assert payouts[3] == 0
        
        # This should fail validation since no one can win
        assert not validate_payouts(pots, payouts, ranks)
    
    
    def test_complex_all_in_scenario(self):
        """Test complex all-in scenario with multiple tiers."""
        # Setup: Multiple all-ins at different levels
        # A=50, B=100, C=150, D=200, E=250
        contributions = {1: 50, 2: 100, 3: 150, 4: 200, 5: 250}
        pm = PotManager(set(contributions.keys()))
        
        for pid, amount in contributions.items():
            pm.post(pid, amount)
        
        pots = pm.build_pots()
        
        # Should create 5 pots:
        # Pot 1: 250 (50 × 5) - all eligible
        # Pot 2: 200 (50 × 4) - B,C,D,E eligible
        # Pot 3: 150 (50 × 3) - C,D,E eligible
        # Pot 4: 100 (50 × 2) - D,E eligible
        # Pot 5: 50 (50 × 1) - E eligible
        assert len(pots) == 5
        
        assert pots[0].amount_cents == 250
        assert pots[0].eligible == {1, 2, 3, 4, 5}
        
        assert pots[1].amount_cents == 200
        assert pots[1].eligible == {2, 3, 4, 5}
        
        assert pots[2].amount_cents == 150
        assert pots[2].eligible == {3, 4, 5}
        
        assert pots[3].amount_cents == 100
        assert pots[3].eligible == {4, 5}
        
        assert pots[4].amount_cents == 50
        assert pots[4].eligible == {5}
        
        # Test payout resolution: E wins overall
        ranks = {1: 5, 2: 4, 3: 3, 4: 2, 5: 1}  # E wins
        seat_order = [1, 2, 3, 4, 5]
        
        payouts = resolve_payouts(pots, ranks, seat_order)
        
        # E should win all pots: 250 + 200 + 150 + 100 + 50 = 750
        assert payouts[5] == 750
        assert payouts[1] == 0
        assert payouts[2] == 0
        assert payouts[3] == 0
        assert payouts[4] == 0
        
        # Verify invariants
        assert sum(pot.amount_cents for pot in pots) == sum(contributions.values())
        assert sum(payouts.values()) == sum(contributions.values())
        assert validate_payouts(pots, payouts, ranks)
    
    def test_single_player_pot(self):
        """Test scenario with only one player contributing."""
        # Setup: Only one player contributes
        contributions = {1: 100}
        pm = PotManager(set(contributions.keys()))
        
        pm.post(1, 100)
        
        pots = pm.build_pots()
        
        # Should have one pot with only that player eligible
        assert len(pots) == 1
        assert pots[0].amount_cents == 100
        assert pots[0].eligible == {1}
        
        # Test payout resolution
        ranks = {1: 1}  # Only one player
        seat_order = [1]
        
        payouts = resolve_payouts(pots, ranks, seat_order)
        
        # Player should get all 100 cents
        assert payouts[1] == 100
        
        # Verify invariants
        assert sum(pot.amount_cents for pot in pots) == sum(contributions.values())
        assert sum(payouts.values()) == sum(contributions.values())
        assert validate_payouts(pots, payouts, ranks) 