#!/usr/bin/env python3
"""
Test script demonstrating agent swapping functionality.

This script shows how different agent types (human, scripted, rule-based)
can be swapped without changing the engine code.
"""


from quads.engine.agent import HumanAgent, RuleBasedAgent, ScriptedAgent
from quads.engine.conn import get_conn
from quads.engine.enums import ActionType
from quads.engine.player import Player
from quads.engine.poker_env import PokerEnv


def create_test_players() -> list[Player]:
    """Create test players for demonstration."""
    from quads.engine.controller import Controller, ControllerType
    
    # Create players with different controller types
    players = [
        Player(
            id=1,
            name="Human Player",
            controller=Controller(ControllerType.MANUAL),
            stack=100.0,
            seat_index=0
        ),
        Player(
            id=2,
            name="Scripted Player", 
            controller=Controller(ControllerType.SCRIPT),
            stack=100.0,
            seat_index=1
        ),
        Player(
            id=3,
            name="Rule-Based Player",
            controller=Controller(ControllerType.MANUAL),
            stack=100.0,
            seat_index=2
        )
    ]
    return players


def create_test_agents() -> dict[int, ScriptedAgent]:
    """Create test agents for demonstration."""
    # Scripted actions for player 2
    scripted_actions = [
        {"type": "call"},  # Call preflop
        {"type": "check"},  # Check flop
        {"type": "fold"}   # Fold turn
    ]
    
    agents = {
        1: HumanAgent(player_id=1),
        2: ScriptedAgent(actions=scripted_actions, player_id=2),
        3: RuleBasedAgent(player_id=3)
    }
    return agents


def test_agent_swapping():
    """Test that agents can be swapped without engine changes."""
    print("=== Agent Swapping Test ===")
    
    # Create test components
    players = create_test_players()
    agents = create_test_agents()
    conn = get_conn()
    
    # Create a scripted deck with hole cards
    from quads.deuces.scripted_deck import ScriptedDeck
    script = {
        "hole_cards": [
            ["As", "Kd"],  # Player 1
            ["7h", "7c"],  # Player 2  
            ["Qh", "Jd"]   # Player 3
        ],
        "board": ["2d", "9s", "Jh", "5c", "3d"]
    }
    
    # Create deck sequence (simplified - just use the hole cards and board)
    deck_sequence = ["As", "Kd", "7h", "7c", "Qh", "Jd", "2d", "9s", "Jh", "5c", "3d"]
    deck = ScriptedDeck(deck_sequence)
    
    # Create PokerEnv
    env = PokerEnv(
        players=players,
        hand_id=1,
        deck=deck,
        dealer_index=0,
        game_session_id=1,
        conn=conn,
        agents=agents,
        script=script
    )
    
    print("Created PokerEnv with mixed agent types:")
    print(f"  Player 1: {type(agents[1]).__name__}")
    print(f"  Player 2: {type(agents[2]).__name__}")
    print(f"  Player 3: {type(agents[3]).__name__}")
    print()
    
    # Test reset
    print("Resetting environment...")
    obs, info = env.reset()
    print(f"Initial observation shape: {obs.to_vector().shape}")
    print(f"Initial info: {info}")
    print()
    
    # Test getting valid actions
    print("Testing valid actions...")
    try:
        valid_actions = env.valid_actions()
        print(f"Valid actions: {[action.value for action in valid_actions.actions]}")
        print(f"Amount to call: {valid_actions.amount_to_call}")
        print(f"Can raise: {valid_actions.can_raise}")
    except Exception as e:
        print(f"Error getting valid actions: {e}")
    print()
    
    # Test agent actions
    print("Testing agent actions...")
    for player_id in [1, 2, 3]:
        try:
            if player_id in agents:
                action, confidence = env.get_agent_action(player_id)
                print(f"Player {player_id} ({type(agents[player_id]).__name__}): {action.value} (confidence: {confidence})")
        except Exception as e:
            print(f"Error getting action for player {player_id}: {e}")
    print()
    
    # Test step
    print("Testing step...")
    try:
        obs, reward, done, info = env.step(ActionType.CALL)
        print(f"Step result: reward={reward}, done={done}")
        print(f"Info: {info}")
    except Exception as e:
        print(f"Error stepping: {e}")
    print()
    
    print("=== Agent Swapping Test Complete ===")


def test_scripted_vs_human():
    """Test swapping between scripted and human agents."""
    print("\n=== Scripted vs Human Agent Test ===")
    
    # Create players
    players = create_test_players()
    conn = get_conn()
    
    # Create script for testing
    from quads.deuces.scripted_deck import ScriptedDeck
    script = {
        "hole_cards": [
            ["As", "Kd"],  # Player 1
            ["7h", "7c"],  # Player 2  
            ["Qh", "Jd"]   # Player 3
        ],
        "board": ["2d", "9s", "Jh", "5c", "3d"]
    }
    
    deck_sequence = ["As", "Kd", "7h", "7c", "Qh", "Jd", "2d", "9s", "Jh", "5c", "3d"]
    deck = ScriptedDeck(deck_sequence)
    
    # Test 1: All scripted agents
    print("Test 1: All scripted agents")
    scripted_agents = {
        1: ScriptedAgent([{"type": "call"}, {"type": "check"}, {"type": "check"}, {"type": "check"}], 1),
        2: ScriptedAgent([{"type": "fold"}], 2),
        3: ScriptedAgent([{"type": "call"}, {"type": "check"}, {"type": "check"}, {"type": "check"}], 3)
    }
    
    env1 = PokerEnv(
        players=players,
        hand_id=2,
        deck=deck,
        dealer_index=0,
        game_session_id=2,
        conn=conn,
        agents=scripted_agents,
        script=script
    )
    
    obs, info = env1.reset()
    print(f"Scripted env reset successful: {info}")
    
    # Test 2: Mix of human and scripted
    print("\nTest 2: Mix of human and scripted agents")
    mixed_agents = {
        1: HumanAgent(1),
        2: ScriptedAgent([{"type": "fold"}], 2),
        3: RuleBasedAgent(3)
    }
    
    env2 = PokerEnv(
        players=players,
        hand_id=3,
        deck=deck,
        dealer_index=0,
        game_session_id=3,
        conn=conn,
        agents=mixed_agents,
        script=script
    )
    
    obs, info = env2.reset()
    print(f"Mixed env reset successful: {info}")
    
    print("=== Scripted vs Human Test Complete ===")


if __name__ == "__main__":
    test_agent_swapping()
    test_scripted_vs_human()
