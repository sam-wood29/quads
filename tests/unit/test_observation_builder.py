"""
Comprehensive tests for ObservationBuilder.

Tests all feature categories, edge cases, and validation logic.
"""

import pytest
import numpy as np
from quads.engine.action_data import GameStateSnapshot
from quads.engine.enums import Phase
from quads.engine.money import to_cents
from quads.engine.observation import ObservationBuilder, ObservationSchema, build_observation
from quads.engine.player import Position


class TestObservationBuilder:
    """Test ObservationBuilder functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.builder = ObservationBuilder(small_blind=0.25, big_blind=0.50)
        self.big_blind_cents = to_cents(0.50)
    
    def create_test_state(self, phase=Phase.PREFLOP, pot_cents=1000, highest_bet=0, 
                         last_raise_increment=50, last_aggressor_seat=None,
                         community_cards=None, street_number=1):
        """Create a test GameStateSnapshot."""
        if community_cards is None:
            community_cards = []
            
        return GameStateSnapshot(
            hand_id=1,
            phase=phase,
            pot_cents=pot_cents,
            community_cards=community_cards,
            players=[
                {
                    'id': 1,
                    'name': 'Hero',
                    'stack': 10000,  # $100 stack
                    'position': 'utg',
                    'hole_cards': ['As', 'Kh'],  # AK suited
                    'has_folded': False,
                    'is_all_in': False,
                    'current_bet': 0,
                    'round_contrib': 0,
                    'hand_contrib': 0
                },
                {
                    'id': 2,
                    'name': 'Villain',
                    'stack': 8000,  # $80 stack
                    'position': 'button',
                    'hole_cards': None,  # No hole cards for opponent
                    'has_folded': False,
                    'is_all_in': False,
                    'current_bet': 0,
                    'round_contrib': 0,
                    'hand_contrib': 0
                }
            ],
            highest_bet=highest_bet,
            last_raise_increment=last_raise_increment,
            last_aggressor_seat=last_aggressor_seat,
            street_number=street_number,
            acted_this_round={1: False, 2: False},
            committed_this_round={1: 0, 2: 0}
        )
    
    def test_basic_observation_build(self):
        """Test basic observation building."""
        state = self.create_test_state()
        
        observation = self.builder.build_observation(state, player_id=1)
        
        # Check that observation is created
        assert isinstance(observation, ObservationSchema)
        
        # Check vector conversion
        vector = observation.to_vector()
        assert isinstance(vector, np.ndarray)
        assert vector.dtype == np.float32
        assert len(vector) == observation.total_features
    
    def test_core_features(self):
        """Test core game state features."""
        state = self.create_test_state(phase=Phase.FLOP)
        
        observation = self.builder.build_observation(state, player_id=1)
        
        # Street one-hot (should be flop = index 2)
        assert observation.street_one_hot[2] == 1.0
        assert sum(observation.street_one_hot) == 1.0
        
        # Players remaining
        assert observation.players_remaining == 2
        
        # Hero position one-hot (UTG = index 0)
        assert observation.hero_position_one_hot[0] == 1.0
        assert sum(observation.hero_position_one_hot) == 1.0
    
    def test_pot_betting_features(self):
        """Test pot and betting metrics."""
        state = self.create_test_state(pot_cents=1500, highest_bet=200)
        
        observation = self.builder.build_observation(state, player_id=1)
        
        # Pot in BB
        expected_pot_bb = 1500 / self.big_blind_cents  # 30 BB
        assert observation.pot_in_bb == expected_pot_bb
        
        # Amount to call
        expected_call_bb = 200 / self.big_blind_cents  # 4 BB
        assert observation.amount_to_call_in_bb == expected_call_bb
        
        # Pot odds
        expected_pot_odds = 200 / (1500 + 200)  # 200/1700
        assert abs(observation.pot_odds - expected_pot_odds) < 0.001
        
        # Bet to call ratio
        expected_ratio = 200 / self.big_blind_cents  # 4 BB
        assert observation.bet_to_call_ratio == expected_ratio
    
    def test_stack_features(self):
        """Test stack-related metrics."""
        state = self.create_test_state(pot_cents=1000)
        
        observation = self.builder.build_observation(state, player_id=1)
        
        # Hero stack in BB
        expected_hero_stack_bb = 10000 / self.big_blind_cents  # 200 BB
        assert observation.hero_stack_in_bb == expected_hero_stack_bb
        
        # Effective stack (min of hero 10000 and villain 8000)
        expected_effective_stack_bb = 8000 / self.big_blind_cents  # 160 BB
        assert observation.effective_stack_in_bb == expected_effective_stack_bb
        
        # SPR
        expected_spr = 8000 / 1000  # 8.0
        assert observation.spr == expected_spr
    
    def test_preflop_features(self):
        """Test preflop hand features."""
        state = self.create_test_state()
        
        observation = self.builder.build_observation(state, player_id=1)
        
        # AK offsuit features (As, Kh are different suits)
        assert observation.is_pair == 0  # Not a pair
        assert observation.is_suited == 0  # Not suited (spades vs hearts)
        assert observation.gap == 1  # A to K gap
        assert observation.high_rank == 14  # Ace
        assert observation.low_rank == 13  # King
        
        # Chen score should be high for AK offsuit
        assert observation.chen_score > 10
        
        # Hand class
        assert observation.pf_hand_class == "AKo"
        
        # Hand strength percentile should be high
        assert observation.hand_strength_percentile > 0.8
    
    def test_preflop_features_pair(self):
        """Test preflop features for a pair."""
        state = self.create_test_state()
        # Modify hero to have a pair
        state.players[0]['hole_cards'] = ['As', 'Ah']
        
        observation = self.builder.build_observation(state, player_id=1)
        
        assert observation.is_pair == 1  # Is a pair
        assert observation.is_suited == 0  # Not suited (As, Ah are different suits)
        assert observation.gap == 0  # No gap
        assert observation.high_rank == 14  # Ace
        assert observation.low_rank == 14  # Ace
        
        # Chen score should be very high for AA
        assert observation.chen_score > 15
        
        assert observation.pf_hand_class == "AAo"  # As, Ah are different suits
    
    def test_preflop_features_no_hole_cards(self):
        """Test preflop features when no hole cards."""
        state = self.create_test_state()
        # Remove hole cards
        state.players[0]['hole_cards'] = None
        
        observation = self.builder.build_observation(state, player_id=1)
        
        # Should return default values
        assert observation.is_pair == 0
        assert observation.is_suited == 0
        assert observation.gap == 0
        assert observation.high_rank == 2
        assert observation.low_rank == 2
        assert observation.chen_score == 0.0
        assert observation.pf_hand_class == "XX"
        assert observation.hand_strength_percentile == 0.0
    
    def test_betting_history_features(self):
        """Test betting history flags."""
        state = self.create_test_state(
            last_raise_increment=100,
            last_aggressor_seat=1  # Hero is aggressor
        )
        
        observation = self.builder.build_observation(state, player_id=1)
        
        # Last raise increment in BB
        expected_increment_bb = 100 / self.big_blind_cents  # 2 BB
        assert observation.last_raise_increment_in_bb == expected_increment_bb
        
        # Is aggressor
        assert observation.is_aggressor == 1
        
        # Has position (UTG doesn't have position)
        assert observation.has_position == 0
    
    def test_board_texture_features(self):
        """Test board texture analysis."""
        # Test paired board
        state = self.create_test_state(
            phase=Phase.FLOP,
            community_cards=['As', 'Ah', 'Kd']
        )
        
        observation = self.builder.build_observation(state, player_id=1)
        
        assert observation.board_paired == 1  # Paired board
        assert observation.board_monotone == 0  # Not monotone
        assert observation.board_two_tone == 0  # Not two-tone
        assert observation.top_board_rank == 14  # Ace is highest
    
    def test_board_texture_monotone(self):
        """Test monotone board."""
        state = self.create_test_state(
            phase=Phase.FLOP,
            community_cards=['As', 'Ks', 'Qs']  # All spades
        )
        
        observation = self.builder.build_observation(state, player_id=1)
        
        assert observation.board_monotone == 1  # Monotone
        assert observation.board_two_tone == 0  # Not two-tone
    
    def test_board_texture_two_tone(self):
        """Test two-tone board."""
        state = self.create_test_state(
            phase=Phase.FLOP,
            community_cards=['As', 'Ks', 'Qh']  # Two suits
        )
        
        observation = self.builder.build_observation(state, player_id=1)
        
        assert observation.board_two_tone == 1  # Two-tone
        assert observation.board_monotone == 0  # Not monotone
    
    def test_board_texture_straighty(self):
        """Test straighty board."""
        state = self.create_test_state(
            phase=Phase.FLOP,
            community_cards=['9s', 'Ts', 'Jh']  # Connected
        )
        
        observation = self.builder.build_observation(state, player_id=1)
        
        # Should have high straighty index
        assert observation.straighty_index > 0.5
    
    def test_additional_features(self):
        """Test additional contextual features."""
        state = self.create_test_state(street_number=2)
        
        observation = self.builder.build_observation(state, player_id=1)
        
        # Players acted this street
        assert observation.players_acted_this_street == 0
        
        # Street number
        assert observation.street_number == 2
        
        # Is all-in
        assert observation.is_all_in == 0
        
        # Stack depth category (200 BB = ultra deep = 4)
        assert observation.stack_depth_category == 4
    
    def test_all_in_scenario(self):
        """Test all-in scenario."""
        state = self.create_test_state()
        # Make hero all-in
        state.players[0]['is_all_in'] = True
        state.players[0]['stack'] = 0
        
        observation = self.builder.build_observation(state, player_id=1)
        
        assert observation.is_all_in == 1
        assert observation.hero_stack_in_bb == 0
        assert observation.spr == 0
    
    def test_short_stack_scenario(self):
        """Test short stack scenario."""
        state = self.create_test_state()
        # Make hero short stacked
        state.players[0]['stack'] = 500  # $5 = 10 BB
        
        observation = self.builder.build_observation(state, player_id=1)
        
        assert observation.hero_stack_in_bb == 10
        assert observation.stack_depth_category == 0  # Shallow
    
    def test_no_information_leakage(self):
        """Test that no opponent hole cards are leaked."""
        state = self.create_test_state()
        # Add hole cards to opponent (should cause error)
        state.players[1]['hole_cards'] = ['Qs', 'Qh']
        
        with pytest.raises(ValueError, match="Information leakage detected"):
            self.builder.build_observation(state, player_id=1)
    
    def test_edge_case_zero_pot(self):
        """Test edge case with zero pot."""
        state = self.create_test_state(pot_cents=0)
        
        observation = self.builder.build_observation(state, player_id=1)
        
        assert observation.pot_in_bb == 0
        assert observation.spr == 0  # Should handle division by zero
    
    def test_edge_case_no_opponents(self):
        """Test edge case with no opponents."""
        # Create state with only hero
        state = GameStateSnapshot(
            hand_id=1,
            phase=Phase.PREFLOP,
            pot_cents=1000,
            community_cards=[],
            players=[{
                'id': 1,
                'name': 'Hero',
                'stack': 10000,
                'position': 'utg',
                'hole_cards': ['As', 'Kh'],
                'has_folded': False,
                'is_all_in': False,
                'current_bet': 0,
                'round_contrib': 0,
                'hand_contrib': 0
            }],
            highest_bet=0,
            last_raise_increment=50,
            last_aggressor_seat=None,
            street_number=1,
            acted_this_round={1: False},
            committed_this_round={1: 0}
        )
        
        observation = self.builder.build_observation(state, player_id=1)
        
        assert observation.players_remaining == 1
        # Effective stack should be hero's stack when no opponents
        assert observation.effective_stack_in_bb == observation.hero_stack_in_bb
    
    def test_different_phases(self):
        """Test observation building across different phases."""
        phases = [Phase.DEAL, Phase.PREFLOP, Phase.FLOP, Phase.TURN, Phase.RIVER]
        
        for phase in phases:
            state = self.create_test_state(phase=phase)
            observation = self.builder.build_observation(state, player_id=1)
            
            # Check that street one-hot is correct
            phase_idx = self.builder.street_to_index[phase]
            assert observation.street_one_hot[phase_idx] == 1.0
    
    def test_different_positions(self):
        """Test observation building for different positions."""
        positions = ['utg', 'button', 'sb', 'bb']
        
        for position in positions:
            state = self.create_test_state()
            state.players[0]['position'] = position
            
            observation = self.builder.build_observation(state, player_id=1)
            
            # Check that position one-hot is correct
            if position in self.builder.position_to_index:
                pos_idx = self.builder.position_to_index[position]
                assert observation.hero_position_one_hot[pos_idx] == 1.0
    
    def test_chen_score_calculations(self):
        """Test Chen score calculations for various hands."""
        test_cases = [
            ('As', 'Ah', 20.0),  # AA offsuit (different suits)
            ('Ks', 'Kh', 16.0),  # KK offsuit (different suits)
            ('As', 'Kd', 11.0),  # AK offsuit
            ('7s', '2h', 0.5),   # 72 offsuit (very low score)
        ]
        
        for card1, card2, expected_min_score in test_cases:
            state = self.create_test_state()
            state.players[0]['hole_cards'] = [card1, card2]
            
            observation = self.builder.build_observation(state, player_id=1)
            
            assert observation.chen_score >= expected_min_score
    
    def test_hand_class_generation(self):
        """Test hand class generation."""
        test_cases = [
            (['As', 'Kh'], 'AKo'),  # Different suits
            (['As', 'Kd'], 'AKo'),  # Different suits
            (['7s', '2h'], '72o'),  # Different suits
            (['Qs', 'Qh'], 'QQo'),  # Different suits
        ]
        
        for hole_cards, expected_class in test_cases:
            state = self.create_test_state()
            state.players[0]['hole_cards'] = hole_cards
            
            observation = self.builder.build_observation(state, player_id=1)
            
            assert observation.pf_hand_class == expected_class
    
    def test_observation_vector_consistency(self):
        """Test that observation vectors are consistent."""
        state = self.create_test_state()
        
        # Build observation multiple times
        obs1 = self.builder.build_observation(state, player_id=1)
        obs2 = self.builder.build_observation(state, player_id=1)
        
        vector1 = obs1.to_vector()
        vector2 = obs2.to_vector()
        
        # Should be identical
        assert np.array_equal(vector1, vector2)
    
    def test_observation_vector_size(self):
        """Test that observation vector has correct size."""
        state = self.create_test_state()
        observation = self.builder.build_observation(state, player_id=1)
        vector = observation.to_vector()
        
        assert len(vector) == observation.total_features
        assert len(vector) == 45  # Expected total features


class TestConvenienceFunction:
    """Test the convenience function."""
    
    def test_build_observation_function(self):
        """Test the build_observation convenience function."""
        builder = ObservationBuilder(small_blind=0.25, big_blind=0.50)
        
        state = GameStateSnapshot(
            hand_id=1,
            phase=Phase.PREFLOP,
            pot_cents=1000,
            community_cards=[],
            players=[{
                'id': 1,
                'name': 'Hero',
                'stack': 10000,
                'position': 'utg',
                'hole_cards': ['As', 'Kh'],
                'has_folded': False,
                'is_all_in': False,
                'current_bet': 0,
                'round_contrib': 0,
                'hand_contrib': 0
            }],
            highest_bet=0,
            last_raise_increment=50,
            last_aggressor_seat=None,
            street_number=1,
            acted_this_round={1: False},
            committed_this_round={1: 0}
        )
        
        vector = build_observation(state, player_id=1)
        
        assert isinstance(vector, np.ndarray)
        assert vector.dtype == np.float32
        assert len(vector) == 45


class TestEdgeCases:
    """Test edge cases and error conditions."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.builder = ObservationBuilder()
    
    def test_invalid_player_id(self):
        """Test with invalid player ID."""
        state = GameStateSnapshot(
            hand_id=1,
            phase=Phase.PREFLOP,
            pot_cents=1000,
            community_cards=[],
            players=[{
                'id': 1,
                'name': 'Hero',
                'stack': 10000,
                'position': 'utg',
                'hole_cards': ['As', 'Kh'],
                'has_folded': False,
                'is_all_in': False,
                'current_bet': 0,
                'round_contrib': 0,
                'hand_contrib': 0
            }],
            highest_bet=0,
            last_raise_increment=50,
            last_aggressor_seat=None,
            street_number=1,
            acted_this_round={1: False},
            committed_this_round={1: 0}
        )
        
        with pytest.raises(ValueError, match="Information leakage detected"):
            self.builder.build_observation(state, player_id=999)
    
    def test_empty_state(self):
        """Test with empty state."""
        state = GameStateSnapshot(
            hand_id=1,
            phase=Phase.PREFLOP,
            pot_cents=0,
            community_cards=[],
            players=[],
            highest_bet=0,
            last_raise_increment=0,
            last_aggressor_seat=None,
            street_number=0,
            acted_this_round={},
            committed_this_round={}
        )
        
        with pytest.raises(ValueError, match="Player 1 not found"):
            self.builder.build_observation(state, player_id=1)
