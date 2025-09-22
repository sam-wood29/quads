"""
Tests for discrete and non-discrete raise amount generation.

These tests validate that both discrete bucket and non-discrete increment systems
work correctly across different streets, stack sizes, and betting scenarios.
"""

from quads.engine.action_data import GameStateSnapshot
from quads.engine.enums import Phase
from quads.engine.money import to_cents
from quads.engine.rules_engine import RulesEngine


class TestDiscreteRaiseBuckets:
    """Test discrete raise bucket generation."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.rules_engine = RulesEngine(small_blind=0.25, big_blind=0.50)
        self.small_blind_cents = to_cents(0.25)
        self.big_blind_cents = to_cents(0.50)
    
    def create_test_state(self, highest_bet_cents=0, pot_cents=0, last_raise_increment_cents=None, phase=Phase.PREFLOP):
        """Create a test GameStateSnapshot."""
        if last_raise_increment_cents is None:
            last_raise_increment_cents = self.big_blind_cents
            
        return GameStateSnapshot(
            hand_id=1,
            phase=phase,
            pot_cents=pot_cents,
            community_cards=[],
            players=[{
                'id': 1,
                'name': 'TestPlayer',
                'stack': 10000,  # $100 stack
                'position': 'utg',
                'hole_cards': None,
                'has_folded': False,
                'is_all_in': False,
                'current_bet': 0,
                'round_contrib': 0,
                'hand_contrib': 0
            }],
            highest_bet=highest_bet_cents,
            last_raise_increment=last_raise_increment_cents,
            last_aggressor_seat=None,
            street_number=1,
            acted_this_round={1: False},
            committed_this_round={1: 0}
        )
    
    def test_preflop_no_bet_buckets(self):
        """Test bucket generation preflop with no bet."""
        state = self.create_test_state(highest_bet_cents=0, pot_cents=150)  # $1.50 pot
        
        buckets = self.rules_engine.get_discrete_raise_amounts(
            min_raise=self.big_blind_cents,  # $0.50 min raise
            max_raise=10000,  # $100 max (full stack)
            state=state,
            player_id=1
        )
        
        # Expected buckets: [min_raise, 2.5x_open, 3x_open, pot, all_in]
        # Note: 3x_open and pot are both 150, so only one instance is kept
        expected = [
            self.big_blind_cents,  # $0.50 min raise
            int(self.big_blind_cents * 2.5),  # $1.25 (2.5x BB)
            int(self.big_blind_cents * 3.0),  # $1.50 (3x BB) - same as pot
            10000  # $100 all-in
        ]
        
        assert buckets == expected
    
    def test_preflop_with_bet_buckets(self):
        """Test bucket generation preflop with existing bet."""
        state = self.create_test_state(highest_bet_cents=200, pot_cents=400)  # $2 bet, $4 pot
        
        buckets = self.rules_engine.get_discrete_raise_amounts(
            min_raise=400,  # $4 min raise (bet + last_raise_increment)
            max_raise=10000,  # $100 max
            state=state,
            player_id=1
        )
        
        # Expected buckets: [min_raise, 2.5x_open, 3x_open, pot, all_in]
        # Note: pot size (400) equals min_raise (400), so it's filtered out
        expected = [
            400,  # $4 min raise
            int(400 * 2.5),  # $10 (2.5x min raise)
            int(400 * 3.0),  # $12 (3x min raise)
            10000  # $100 all-in
        ]
        
        assert buckets == expected
    
    def test_short_stack_filtering(self):
        """Test that buckets are filtered when player has short stack."""
        state = self.create_test_state(highest_bet_cents=0, pot_cents=150)
        
        # Modify player to have short stack
        state.players[0]['stack'] = 100  # $1 stack
        
        buckets = self.rules_engine.get_discrete_raise_amounts(
            min_raise=self.big_blind_cents,
            max_raise=100,  # Limited by stack
            state=state,
            player_id=1
        )
        
        # Should only include buckets <= $1
        expected = [
            self.big_blind_cents,  # $0.50 min raise
            100  # $1 all-in
        ]
        
        assert buckets == expected
    
    def test_pot_size_bucket(self):
        """Test pot size bucket calculation."""
        state = self.create_test_state(highest_bet_cents=0, pot_cents=750)  # $7.50 pot
        
        buckets = self.rules_engine.get_discrete_raise_amounts(
            min_raise=self.big_blind_cents,
            max_raise=10000,
            state=state,
            player_id=1
        )
        
        # Pot size should be included
        assert 750 in buckets
    
    def test_multiplier_buckets(self):
        """Test 2.5x and 3x multiplier buckets."""
        state = self.create_test_state(highest_bet_cents=0, pot_cents=100)
        
        buckets = self.rules_engine.get_discrete_raise_amounts(
            min_raise=self.big_blind_cents,
            max_raise=10000,
            state=state,
            player_id=1
        )
        
        # Check multipliers are calculated correctly
        expected_2_5x = int(self.big_blind_cents * 2.5)  # $1.25
        expected_3x = int(self.big_blind_cents * 3.0)    # $1.50
        
        assert expected_2_5x in buckets
        assert expected_3x in buckets
    
    def test_buckets_sorted(self):
        """Test that buckets are returned in sorted order."""
        state = self.create_test_state(highest_bet_cents=0, pot_cents=100)
        
        buckets = self.rules_engine.get_discrete_raise_amounts(
            min_raise=self.big_blind_cents,
            max_raise=10000,
            state=state,
            player_id=1
        )
        
        # Should be sorted ascending
        assert buckets == sorted(buckets)
    
    def test_no_duplicate_buckets(self):
        """Test that no duplicate amounts are returned."""
        state = self.create_test_state(highest_bet_cents=0, pot_cents=100)
        
        buckets = self.rules_engine.get_discrete_raise_amounts(
            min_raise=self.big_blind_cents,
            max_raise=10000,
            state=state,
            player_id=1
        )
        
        # No duplicates
        assert len(buckets) == len(set(buckets))
    
    def test_flop_street_buckets(self):
        """Test bucket generation on flop street."""
        state = self.create_test_state(highest_bet_cents=0, pot_cents=200, phase=Phase.FLOP)
        
        buckets = self.rules_engine.get_discrete_raise_amounts(
            min_raise=self.big_blind_cents,
            max_raise=10000,
            state=state,
            player_id=1
        )
        
        # Should work the same as preflop
        assert len(buckets) > 0
        assert self.big_blind_cents in buckets  # Min raise should be present
    
    def test_edge_case_zero_pot(self):
        """Test bucket generation with zero pot."""
        state = self.create_test_state(highest_bet_cents=0, pot_cents=0)
        
        buckets = self.rules_engine.get_discrete_raise_amounts(
            min_raise=self.big_blind_cents,
            max_raise=10000,
            state=state,
            player_id=1
        )
        
        # Should still work, pot bucket will be 0 (but filtered out since it's < min_raise)
        assert len(buckets) > 0
        # Pot size bucket (0) should be filtered out since it's less than min_raise (50)
        assert 0 not in buckets
    
    def test_edge_case_min_raise_equals_max(self):
        """Test when min raise equals max raise."""
        state = self.create_test_state(highest_bet_cents=0, pot_cents=100)
        
        buckets = self.rules_engine._generate_raise_amounts(
            min_raise=10000,  # Min raise = full stack
            max_raise=10000,  # Max raise = full stack
            state=state,
            player_id=1
        )
        
        # Should only return the min raise
        assert buckets == [10000]
    
    def test_calculate_2_5x_open_no_bet(self):
        """Test 2.5x calculation with no existing bet."""
        state = self.create_test_state(highest_bet_cents=0)
        
        result = self.rules_engine._calculate_2_5x_open(state, self.big_blind_cents)
        expected = int(self.big_blind_cents * 2.5)
        
        assert result == expected
    
    def test_calculate_2_5x_open_with_bet(self):
        """Test 2.5x calculation with existing bet."""
        state = self.create_test_state(highest_bet_cents=200)
        
        result = self.rules_engine._calculate_2_5x_open(state, 400)  # min_raise = 400
        expected = int(400 * 2.5)
        
        assert result == expected
    
    def test_calculate_3x_open_no_bet(self):
        """Test 3x calculation with no existing bet."""
        state = self.create_test_state(highest_bet_cents=0)
        
        result = self.rules_engine._calculate_3x_open(state, self.big_blind_cents)
        expected = int(self.big_blind_cents * 3.0)
        
        assert result == expected
    
    def test_calculate_3x_open_with_bet(self):
        """Test 3x calculation with existing bet."""
        state = self.create_test_state(highest_bet_cents=200)
        
        result = self.rules_engine._calculate_3x_open(state, 400)  # min_raise = 400
        expected = int(400 * 3.0)
        
        assert result == expected


class TestNonDiscreteRaiseAmounts:
    """Test non-discrete raise amount generation."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.rules_engine = RulesEngine(small_blind=0.25, big_blind=0.50)
        self.small_blind_cents = to_cents(0.25)
        self.big_blind_cents = to_cents(0.50)
    
    def create_test_state(self, highest_bet_cents=0, pot_cents=0, last_raise_increment_cents=None, phase=Phase.PREFLOP):
        """Create a test GameStateSnapshot."""
        if last_raise_increment_cents is None:
            last_raise_increment_cents = self.big_blind_cents
            
        return GameStateSnapshot(
            hand_id=1,
            phase=phase,
            pot_cents=pot_cents,
            community_cards=[],
            players=[{
                'id': 1,
                'name': 'TestPlayer',
                'stack': 10000,  # $100 stack
                'position': 'utg',
                'hole_cards': None,
                'has_folded': False,
                'is_all_in': False,
                'current_bet': 0,
                'round_contrib': 0,
                'hand_contrib': 0
            }],
            highest_bet=highest_bet_cents,
            last_raise_increment=last_raise_increment_cents,
            last_aggressor_seat=None,
            street_number=1,
            acted_this_round={1: False},
            committed_this_round={1: 0}
        )
    
    def test_preflop_no_bet_increments(self):
        """Test non-discrete generation preflop with no bet."""
        state = self.create_test_state(highest_bet_cents=0, pot_cents=150)
        
        amounts = self.rules_engine.get_non_discrete_raise_amounts(
            min_raise=self.big_blind_cents,  # $0.50 min raise
            max_raise=1000,  # $10 max (limited for test)
            state=state,
            player_id=1
        )
        
        # Should generate increments of $0.25 (small blind)
        expected = [50, 75, 100, 125, 150, 175, 200, 225, 250, 275, 300, 325, 350, 375, 400, 425, 450, 475, 500, 525, 550, 575, 600, 625, 650, 675, 700, 725, 750, 775, 800, 825, 850, 875, 900, 925, 950, 975, 1000]
        
        assert amounts == expected
    
    def test_preflop_with_bet_increments(self):
        """Test non-discrete generation preflop with existing bet."""
        state = self.create_test_state(highest_bet_cents=200, pot_cents=400)
        
        amounts = self.rules_engine.get_non_discrete_raise_amounts(
            min_raise=400,  # $4 min raise
            max_raise=1000,  # $10 max (limited for test)
            state=state,
            player_id=1
        )
        
        # Should generate increments of $0.25 starting from $4.00
        expected = [400, 425, 450, 475, 500, 525, 550, 575, 600, 625, 650, 675, 700, 725, 750, 775, 800, 825, 850, 875, 900, 925, 950, 975, 1000]
        
        assert amounts == expected
    
    def test_short_stack_increments(self):
        """Test non-discrete generation with short stack."""
        state = self.create_test_state(highest_bet_cents=0, pot_cents=100)
        
        # Modify player to have short stack
        state.players[0]['stack'] = 200  # $2 stack
        
        amounts = self.rules_engine.get_non_discrete_raise_amounts(
            min_raise=self.big_blind_cents,
            max_raise=200,  # Limited by stack
            state=state,
            player_id=1
        )
        
        # Should only include amounts <= $2
        expected = [50, 75, 100, 125, 150, 175, 200]
        
        assert amounts == expected
    
    def test_increments_sorted(self):
        """Test that non-discrete amounts are returned in sorted order."""
        state = self.create_test_state(highest_bet_cents=0, pot_cents=100)
        
        amounts = self.rules_engine.get_non_discrete_raise_amounts(
            min_raise=self.big_blind_cents,
            max_raise=1000,
            state=state,
            player_id=1
        )
        
        # Should be sorted ascending
        assert amounts == sorted(amounts)
    
    def test_increments_no_duplicates(self):
        """Test that no duplicate amounts are returned."""
        state = self.create_test_state(highest_bet_cents=0, pot_cents=100)
        
        amounts = self.rules_engine.get_non_discrete_raise_amounts(
            min_raise=self.big_blind_cents,
            max_raise=1000,
            state=state,
            player_id=1
        )
        
        # No duplicates
        assert len(amounts) == len(set(amounts))
    
    def test_flop_street_increments(self):
        """Test non-discrete generation on flop street."""
        state = self.create_test_state(highest_bet_cents=0, pot_cents=200, phase=Phase.FLOP)
        
        amounts = self.rules_engine.get_non_discrete_raise_amounts(
            min_raise=self.big_blind_cents,
            max_raise=1000,
            state=state,
            player_id=1
        )
        
        # Should work the same as preflop
        assert len(amounts) > 0
        assert self.big_blind_cents in amounts  # Min raise should be present
    
    def test_edge_case_min_raise_equals_max(self):
        """Test when min raise equals max raise."""
        state = self.create_test_state(highest_bet_cents=0, pot_cents=100)
        
        amounts = self.rules_engine.get_non_discrete_raise_amounts(
            min_raise=10000,  # Min raise = full stack
            max_raise=10000,  # Max raise = full stack
            state=state,
            player_id=1
        )
        
        # Should only return the min raise
        assert amounts == [10000]


class TestHandDiscreteRaiseBuckets:
    """Test discrete raise bucket generation in Hand class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        # This would require more complex setup with actual Hand instance
        # For now, we'll focus on the RulesEngine tests above
        pass
    
    # TODO: Add Hand-specific tests when needed
    # These would test the Hand._generate_raise_amounts method
    # and ensure consistency with RulesEngine implementation
