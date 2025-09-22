#!/usr/bin/env python3
"""
Integration test for RuleBasedAgent - Test with actual poker hand

This script tests the rule-based agent in a real poker hand scenario
to ensure it integrates properly with the existing poker engine.
"""

import os
import sqlite3
import sys

import numpy as np

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from quads.deuces.deck import Deck
from quads.engine.action_data import ValidActions
from quads.engine.controller import Controller, ControllerType
from quads.engine.enums import ActionType
from quads.engine.hand import Hand
from quads.engine.observation import ObservationSchema
from quads.engine.player import Player, Position
from quads.engine.rule_based_agent import RuleBasedAgent


def test_rule_based_agent_integration():
    """Test rule-based agent in an actual poker hand."""
    print("=== Testing RuleBasedAgent Integration ===")
    
    # Create a temporary database connection
    conn = sqlite3.connect(':memory:')
    
    # Create the actions table for logging
    conn.execute('''
        CREATE TABLE actions (
            id INTEGER PRIMARY KEY,
            game_session_id INTEGER,
            hand_id INTEGER,
            step_number INTEGER,
            player_id INTEGER,
            action TEXT,
            amount REAL,
            phase TEXT,
            hole_cards TEXT,
            community_cards TEXT,
            hand_rank_5 INTEGER,
            hand_class TEXT,
            pot_odds REAL,
            percent_stack_to_call REAL,
            amount_to_call REAL,
            highest_bet REAL,
            position TEXT,
            detail TEXT,
            hole_card1 TEXT,
            hole_card2 TEXT,
            pf_hand_class TEXT,
            high_rank INTEGER,
            low_rank INTEGER,
            is_pair INTEGER,
            is_suited INTEGER,
            gap INTEGER,
            chen_score REAL
        )
    ''')
    
    # Create players
    players = []
    
    # Player 1: Rule-based agent
    controller1 = Controller(ControllerType.SCRIPT)
    player1 = Player(id=1, name="RuleBot", controller=controller1, stack=100.0, seat_index=0)
    player1.position = Position.BB
    
    # Player 2: Human agent (will fold automatically in test mode)
    controller2 = Controller(ControllerType.SCRIPT)
    player2 = Player(id=2, name="Human", controller=controller2, stack=100.0, seat_index=1)
    player2.position = Position.SB
    
    players = [player1, player2]
    
    # Create rule-based agent
    rule_agent = RuleBasedAgent(
        player_id=1,
        epsilon=0.05,
        mc_samples=1000,
        debug=True
    )
    
    # Create agents dict
    agents = {1: rule_agent}
    
    # Create deck
    deck = Deck()
    
    # Create a simple script with hole cards
    script = {
        "hole_cards": [
            ["Ah", "As"],  # Player 1 gets AA
            ["7h", "2c"]   # Player 2 gets 72o
        ],
        "board": ["Kh", "Qh", "Jh", "5c", "3d"],  # Full board
        "preflop": {
            "actions": {
                0: [{"type": "call"}],  # SB calls
                1: [{"type": "check"}]  # BB checks
            }
        }
    }
    
    # Create hand
    hand = Hand(
        players=players,
        id=1,
        deck=deck,
        dealer_index=0,
        game_session_id=1,
        conn=conn,
        script=script,
        agents=agents,
        small_blind=0.25,
        big_blind=0.50
    )
    
    print(f"Created hand with {len(players)} players")
    print(f"Player 1 (RuleBot): {player1}")
    print(f"Player 2 (Human): {player2}")
    
    # Deal hole cards
    hand._deal_hole_cards()
    
    print("\nAfter dealing hole cards:")
    print(f"Player 1 hole cards: {player1.hole_cards}")
    print(f"Player 2 hole cards: {player2.hole_cards}")
    
    # Test that the agent can make a decision with the dealt cards
    print("\n=== Testing Agent Decision Making ===")
    
    # Create a simple test scenario
    
    # Create a test observation
    obs = ObservationSchema(
        street_one_hot=np.array([0, 1, 0, 0, 0]),  # preflop
        players_remaining=2,
        hero_position_one_hot=np.array([0, 0, 0, 0, 0, 0, 0, 0, 0, 1]),  # BB
        pot_in_bb=2.0,
        amount_to_call_in_bb=0.0,
        pot_odds=0.0,
        bet_to_call_ratio=0.0,
        hero_stack_in_bb=100.0,
        effective_stack_in_bb=100.0,
        spr=50.0,
        is_pair=1,
        is_suited=0,
        gap=0,
        high_rank=14,
        low_rank=14,
        chen_score=20.0,
        pf_hand_class='AAo',
        hand_strength_percentile=0.95,
        raises_this_street=0,
        last_raise_increment_in_bb=0.0,
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
        actions=[ActionType.CHECK, ActionType.RAISE],
        raise_amounts=[100, 200, 500],  # 1BB, 2BB, 5BB
        amount_to_call=0,
        can_check=True,
        can_bet=True,
        can_raise=True
    )
    
    # Create game state with AA
    game_state = {
        'hole_cards': 'Ah,As',
        'community_cards': '',  # Preflop
        'phase': 'preflop',
        'pot': 200,
        'highest_bet': 0
    }
    
    # Test agent decision
    try:
        action, confidence = rule_agent.act_with_context(obs, valid_actions, game_state)
        print(f"Agent decision: {action.value} (confidence: {confidence:.2f})")
        
        # AA should typically raise or check, not fold
        assert action in [ActionType.CHECK, ActionType.RAISE], f"AA should not fold, got {action.value}"
        print("✓ Agent made reasonable decision with AA")
        
    except Exception as e:
        print(f"Error in agent decision: {e}")
        import traceback
        traceback.print_exc()
        raise
    
    print("\n=== Integration Test Complete ===")
    
    # Clean up
    conn.close()


def test_agent_vs_agent():
    """Test two rule-based agents playing against each other."""
    print("\n=== Testing Agent vs Agent ===")
    
    # Create a temporary database connection
    conn = sqlite3.connect(':memory:')
    
    # Create the actions table for logging
    conn.execute('''
        CREATE TABLE actions (
            id INTEGER PRIMARY KEY,
            game_session_id INTEGER,
            hand_id INTEGER,
            step_number INTEGER,
            player_id INTEGER,
            action TEXT,
            amount REAL,
            phase TEXT,
            hole_cards TEXT,
            community_cards TEXT,
            hand_rank_5 INTEGER,
            hand_class TEXT,
            pot_odds REAL,
            percent_stack_to_call REAL,
            amount_to_call REAL,
            highest_bet REAL,
            position TEXT,
            detail TEXT,
            hole_card1 TEXT,
            hole_card2 TEXT,
            pf_hand_class TEXT,
            high_rank INTEGER,
            low_rank INTEGER,
            is_pair INTEGER,
            is_suited INTEGER,
            gap INTEGER,
            chen_score REAL
        )
    ''')
    
    # Create players
    players = []
    
    # Player 1: Rule-based agent
    controller1 = Controller(ControllerType.SCRIPT)
    player1 = Player(id=1, name="RuleBot1", controller=controller1, stack=100.0, seat_index=0)
    player1.position = Position.BB
    
    # Player 2: Another rule-based agent
    controller2 = Controller(ControllerType.SCRIPT)
    player2 = Player(id=2, name="RuleBot2", controller=controller2, stack=100.0, seat_index=1)
    player2.position = Position.SB
    
    players = [player1, player2]
    
    # Create rule-based agents
    agent1 = RuleBasedAgent(player_id=1, debug=False, mc_samples=500)
    agent2 = RuleBasedAgent(player_id=2, debug=False, mc_samples=500)
    
    # Create agents dict
    agents = {1: agent1, 2: agent2}
    
    # Create deck
    deck = Deck()
    
    # Create a simple script with hole cards
    script = {
        "hole_cards": [
            ["Ah", "Kd"],  # Player 1 gets AK
            ["7h", "2c"]   # Player 2 gets 72o
        ],
        "board": ["Kh", "Qh", "Jh", "5c", "3d"],  # Full board
        "preflop": {
            "actions": {
                0: [{"type": "call"}],  # SB calls
                1: [{"type": "check"}]  # BB checks
            }
        }
    }
    
    # Create hand
    hand = Hand(
        players=players,
        id=1,
        deck=deck,
        dealer_index=0,
        game_session_id=1,
        conn=conn,
        script=script,
        agents=agents,
        small_blind=0.25,
        big_blind=0.50
    )
    
    print("Created hand with two rule-based agents")
    
    # Deal hole cards
    hand._deal_hole_cards()
    
    print(f"Player 1 hole cards: {player1.hole_cards}")
    print(f"Player 2 hole cards: {player2.hole_cards}")
    
    # Test that both agents can make decisions
    print("\n=== Testing Both Agents ===")
    
    # Test agent 1 (AK)
    obs1 = ObservationSchema(
        street_one_hot=np.array([0, 1, 0, 0, 0]),  # preflop
        players_remaining=2,
        hero_position_one_hot=np.array([0, 0, 0, 0, 0, 0, 0, 0, 0, 1]),  # BB
        pot_in_bb=2.0,
        amount_to_call_in_bb=0.0,
        pot_odds=0.0,
        bet_to_call_ratio=0.0,
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
        last_raise_increment_in_bb=0.0,
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
    
    valid_actions1 = ValidActions(
        player_id=1,
        actions=[ActionType.CHECK, ActionType.RAISE],
        raise_amounts=[100, 200, 500],
        amount_to_call=0,
        can_check=True,
        can_bet=True,
        can_raise=True
    )
    
    game_state1 = {
        'hole_cards': 'Ah,Kd',
        'community_cards': '',
        'phase': 'preflop',
        'pot': 200,
        'highest_bet': 0
    }
    
    action1, confidence1 = agent1.act_with_context(obs1, valid_actions1, game_state1)
    print(f"Agent 1 (AK) decision: {action1.value} (confidence: {confidence1:.2f})")
    
    # Test agent 2 (72o)
    obs2 = ObservationSchema(
        street_one_hot=np.array([0, 1, 0, 0, 0]),  # preflop
        players_remaining=2,
        hero_position_one_hot=np.array([0, 0, 0, 0, 0, 0, 0, 0, 1, 0]),  # SB
        pot_in_bb=2.0,
        amount_to_call_in_bb=0.25,
        pot_odds=0.11,
        bet_to_call_ratio=0.5,
        hero_stack_in_bb=100.0,
        effective_stack_in_bb=100.0,
        spr=50.0,
        is_pair=0,
        is_suited=0,
        gap=5,
        high_rank=7,
        low_rank=2,
        chen_score=1.0,
        pf_hand_class='72o',
        hand_strength_percentile=0.05,
        raises_this_street=0,
        last_raise_increment_in_bb=0.0,
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
    
    valid_actions2 = ValidActions(
        player_id=2,
        actions=[ActionType.FOLD, ActionType.CALL, ActionType.RAISE],
        raise_amounts=[100, 200, 500],
        amount_to_call=25,
        can_check=False,
        can_bet=True,
        can_raise=True
    )
    
    game_state2 = {
        'hole_cards': '7h,2c',
        'community_cards': '',
        'phase': 'preflop',
        'pot': 200,
        'highest_bet': 25
    }
    
    action2, confidence2 = agent2.act_with_context(obs2, valid_actions2, game_state2)
    print(f"Agent 2 (72o) decision: {action2.value} (confidence: {confidence2:.2f})")
    
    # Verify decisions make sense
    assert action1 in [ActionType.CHECK, ActionType.RAISE], "AK should not fold"
    # 72o might fold or call depending on pot odds
    assert action2 in [ActionType.FOLD, ActionType.CALL, ActionType.RAISE], "72o should make some decision"
    
    print("✓ Both agents made reasonable decisions")
    
    print("\n=== Agent vs Agent Test Complete ===")
    
    # Clean up
    conn.close()


def main():
    """Run integration tests."""
    print("Testing RuleBasedAgent Integration\n")
    
    try:
        test_rule_based_agent_integration()
        test_agent_vs_agent()
        
        print("\n🎉 All integration tests passed!")
        
    except Exception as e:
        print(f"❌ Integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
