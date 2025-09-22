#!/usr/bin/env python3
"""
Test script for RuleBasedAgent - Block 12 Implementation

This script tests the rule-based agent's basic functionality:
1. Agent instantiation
2. Card extraction
3. Equity calculation
4. Decision making
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np

from quads.deuces.card import Card
from quads.engine.action_data import ValidActions
from quads.engine.enums import ActionType
from quads.engine.observation import ObservationSchema
from quads.engine.rule_based_agent import RuleBasedAgent


def test_agent_instantiation():
    """Test that the agent can be created with various configurations."""
    print("=== Testing Agent Instantiation ===")
    
    # Test basic instantiation
    agent = RuleBasedAgent(player_id=1)
    assert agent.player_id == 1
    assert agent.epsilon == 0.05
    assert agent.mc_samples == 5000
    print("✓ Basic instantiation works")
    
    # Test custom parameters
    agent = RuleBasedAgent(
        player_id=2,
        epsilon=0.1,
        mc_samples=1000,
        debug=True,
        random_seed=42
    )
    assert agent.player_id == 2
    assert agent.epsilon == 0.1
    assert agent.mc_samples == 1000
    assert agent.debug
    print("✓ Custom parameters work")
    
    print("Agent instantiation tests passed!\n")


def test_card_extraction():
    """Test card extraction from game state."""
    print("=== Testing Card Extraction ===")
    
    agent = RuleBasedAgent(player_id=1, debug=True)
    
    # Test hole card extraction from game state
    game_state = {
        'hole_cards': 'Ah,Kd',
        'community_cards': '7c,8s,9h'
    }
    
    # Create a dummy observation
    obs = ObservationSchema(
        street_one_hot=np.array([0, 1, 0, 0, 0]),  # preflop
        players_remaining=2,
        hero_position_one_hot=np.array([0, 0, 0, 0, 0, 0, 0, 0, 0, 1]),  # BB
        pot_in_bb=2.0,
        amount_to_call_in_bb=1.0,
        pot_odds=0.33,
        bet_to_call_ratio=2.0,
        hero_stack_in_bb=100.0,
        effective_stack_in_bb=100.0,
        spr=50.0,
        is_pair=0,
        is_suited=0,
        gap=12,
        high_rank=14,
        low_rank=13,
        chen_score=8.0,
        pf_hand_class='AKo',
        hand_strength_percentile=0.8,
        raises_this_street=0,
        last_raise_increment_in_bb=1.0,
        is_aggressor=0,
        has_position=0,
        board_paired=0,
        board_monotone=0,
        board_two_tone=0,
        straighty_index=0.0,
        top_board_rank=2,
        board_coordination=0.0,
        players_acted_this_street=0,
        street_number=1,
        is_all_in=0,
        stack_depth_category=3
    )
    
    # Test hole card extraction
    hole_cards = agent._extract_hole_cards(obs, game_state)
    assert hole_cards is not None
    assert len(hole_cards) == 2
    print(f"✓ Hole cards extracted: {[Card.int_to_str(c) for c in hole_cards]}")
    
    # Test board extraction
    board = agent._extract_board(obs, game_state)
    assert board is not None
    assert len(board) == 3
    print(f"✓ Board extracted: {[Card.int_to_str(c) for c in board]}")
    
    print("Card extraction tests passed!\n")


def test_equity_calculation():
    """Test Monte Carlo equity calculation."""
    print("=== Testing Equity Calculation ===")
    
    agent = RuleBasedAgent(player_id=1, mc_samples=1000, debug=True)  # Use fewer samples for testing
    
    # Test with strong hand (AA)
    hole_cards = [Card.new('Ah'), Card.new('As')]
    board = []  # Preflop
    
    equity = agent.estimate_equity(hole_cards, board, num_opponents=1)
    print(f"✓ AA vs random hand equity: {equity:.3f}")
    assert 0.8 <= equity <= 0.9  # AA should have ~85% equity vs random hand
    
    # Test with weak hand (72o)
    hole_cards = [Card.new('7h'), Card.new('2c')]
    equity = agent.estimate_equity(hole_cards, board, num_opponents=1)
    print(f"✓ 72o vs random hand equity: {equity:.3f}")
    assert 0.3 <= equity <= 0.4  # 72o should have ~35% equity vs random hand
    
    print("Equity calculation tests passed!\n")


def test_decision_logic():
    """Test decision making logic."""
    print("=== Testing Decision Logic ===")
    
    agent = RuleBasedAgent(player_id=1, debug=True)
    
    # Create test observation with good pot odds
    obs = ObservationSchema(
        street_one_hot=np.array([0, 1, 0, 0, 0]),  # preflop
        players_remaining=2,
        hero_position_one_hot=np.array([0, 0, 0, 0, 0, 0, 0, 0, 0, 1]),  # BB
        pot_in_bb=10.0,
        amount_to_call_in_bb=2.0,
        pot_odds=0.17,  # Good pot odds
        bet_to_call_ratio=4.0,
        hero_stack_in_bb=100.0,
        effective_stack_in_bb=100.0,
        spr=10.0,
        is_pair=0,
        is_suited=0,
        gap=12,
        high_rank=14,
        low_rank=13,
        chen_score=8.0,
        pf_hand_class='AKo',
        hand_strength_percentile=0.8,
        raises_this_street=0,
        last_raise_increment_in_bb=2.0,
        is_aggressor=0,
        has_position=0,
        board_paired=0,
        board_monotone=0,
        board_two_tone=0,
        straighty_index=0.0,
        top_board_rank=2,
        board_coordination=0.0,
        players_acted_this_street=0,
        street_number=1,
        is_all_in=0,
        stack_depth_category=3
    )
    
    # Create valid actions
    valid_actions = ValidActions(
        player_id=1,
        actions=[ActionType.FOLD, ActionType.CALL, ActionType.RAISE],
        raise_amounts=[400, 1000, 2000],  # 4BB, 10BB, 20BB
        amount_to_call=200,
        can_check=False,
        can_bet=True,
        can_raise=True
    )
    
    # Test decision with high equity
    action, confidence = agent._make_decision(obs, valid_actions, equity=0.8)
    print(f"✓ High equity decision: {action.value} (confidence: {confidence:.2f})")
    assert action in [ActionType.CALL, ActionType.RAISE]  # Should not fold with high equity
    
    # Test decision with low equity
    action, confidence = agent._make_decision(obs, valid_actions, equity=0.1)
    print(f"✓ Low equity decision: {action.value} (confidence: {confidence:.2f})")
    assert action == ActionType.FOLD  # Should fold with low equity
    
    print("Decision logic tests passed!\n")


def test_full_agent_decision():
    """Test the complete agent decision process."""
    print("=== Testing Full Agent Decision ===")
    
    agent = RuleBasedAgent(player_id=1, debug=True, mc_samples=500)
    
    # Create test observation
    obs = ObservationSchema(
        street_one_hot=np.array([0, 1, 0, 0, 0]),  # preflop
        players_remaining=2,
        hero_position_one_hot=np.array([0, 0, 0, 0, 0, 0, 0, 0, 0, 1]),  # BB
        pot_in_bb=3.0,
        amount_to_call_in_bb=1.0,
        pot_odds=0.25,
        bet_to_call_ratio=2.0,
        hero_stack_in_bb=100.0,
        effective_stack_in_bb=100.0,
        spr=33.0,
        is_pair=0,
        is_suited=0,
        gap=12,
        high_rank=14,
        low_rank=13,
        chen_score=8.0,
        pf_hand_class='AKo',
        hand_strength_percentile=0.8,
        raises_this_street=0,
        last_raise_increment_in_bb=1.0,
        is_aggressor=0,
        has_position=0,
        board_paired=0,
        board_monotone=0,
        board_two_tone=0,
        straighty_index=0.0,
        top_board_rank=2,
        board_coordination=0.0,
        players_acted_this_street=0,
        street_number=1,
        is_all_in=0,
        stack_depth_category=3
    )
    
    # Create valid actions
    valid_actions = ValidActions(
        player_id=1,
        actions=[ActionType.FOLD, ActionType.CALL, ActionType.RAISE],
        raise_amounts=[200, 500, 1000],  # 2BB, 5BB, 10BB
        amount_to_call=100,
        can_check=False,
        can_bet=True,
        can_raise=True
    )
    
    # Create game state with AK
    game_state = {
        'hole_cards': 'Ah,Kd',
        'community_cards': '',  # Preflop
        'phase': 'preflop',
        'pot': 300,
        'highest_bet': 100
    }
    
    # Test full decision
    action, confidence = agent.act_with_context(obs, valid_actions, game_state)
    print(f"✓ Full agent decision: {action.value} (confidence: {confidence:.2f})")
    
    # AK should typically raise or call, not fold
    assert action in [ActionType.CALL, ActionType.RAISE]
    
    print("Full agent decision test passed!\n")


def main():
    """Run all tests."""
    print("Testing RuleBasedAgent Implementation\n")
    
    try:
        test_agent_instantiation()
        test_card_extraction()
        test_equity_calculation()
        test_decision_logic()
        test_full_agent_decision()
        
        print("🎉 All tests passed! RuleBasedAgent is working correctly.")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
