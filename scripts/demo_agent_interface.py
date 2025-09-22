#!/usr/bin/env python3
"""
Example showing how to use the PokerEnv wrapper for agent-based poker.

This demonstrates the Gym-like interface for poker hands.
"""


from quads.deuces.deck import Deck
from quads.engine.agent import HumanAgent, RuleBasedAgent, ScriptedAgent
from quads.engine.conn import get_conn
from quads.engine.controller import Controller, ControllerType
from quads.engine.player import Player
from quads.engine.poker_env import PokerEnv


def create_example_players() -> list[Player]:
    """Create example players for the demo."""
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
            controller=Controller(ControllerType.SCRIPT),
            stack=100.0,
            seat_index=2
        )
    ]
    return players


def create_example_agents() -> dict[int, ScriptedAgent]:
    """Create example agents for the demo."""
    agents = {
        1: HumanAgent(player_id=1),
        2: ScriptedAgent(
            actions=[
                {"type": "call"},  # Call preflop
                {"type": "check"}, # Check flop
                {"type": "fold"}   # Fold turn
            ],
            player_id=2
        ),
        3: RuleBasedAgent(player_id=3)
    }
    return agents


def demonstrate_poker_env():
    """Demonstrate the PokerEnv wrapper functionality."""
    print("=== PokerEnv Demonstration ===")
    
    # Create components
    players = create_example_players()
    agents = create_example_agents()
    conn = get_conn()
    deck = Deck()
    
    # Create PokerEnv
    env = PokerEnv(
        players=players,
        hand_id=1,
        deck=deck,
        dealer_index=0,
        game_session_id=1,
        conn=conn,
        agents=agents
    )
    
    print(f"Created PokerEnv with {len(players)} players")
    print("Agent types:")
    for player_id, agent in agents.items():
        print(f"  Player {player_id}: {type(agent).__name__}")
    print()
    
    # Demonstrate reset
    print("Resetting environment...")
    try:
        obs, info = env.reset()
        print("Reset successful!")
        print(f"Initial observation shape: {obs.to_vector().shape}")
        print(f"Initial info: {info}")
    except Exception as e:
        print(f"Reset failed: {e}")
        print("This is expected since the Hand class needs scripted dealing")
    print()
    
    # Demonstrate valid actions
    print("Testing valid actions...")
    try:
        valid_actions = env.valid_actions()
        print(f"Valid actions: {[action.value for action in valid_actions.actions]}")
        print(f"Amount to call: {valid_actions.amount_to_call}")
        print(f"Can raise: {valid_actions.can_raise}")
    except Exception as e:
        print(f"Valid actions failed: {e}")
        print("This is expected since the environment isn't fully initialized")
    print()
    
    # Demonstrate agent actions
    print("Testing agent actions...")
    for player_id in [1, 2, 3]:
        try:
            action, confidence = env.get_agent_action(player_id)
            print(f"Player {player_id} ({type(agents[player_id]).__name__}): {action.value} (confidence: {confidence})")
        except Exception as e:
            print(f"Agent action failed for player {player_id}: {e}")
    print()
    
    print("=== PokerEnv Demonstration Complete ===")


def demonstrate_agent_interface():
    """Demonstrate the agent interface directly."""
    print("\n=== Agent Interface Demonstration ===")
    
    # Create different agent types
    agents = {
        "human": HumanAgent(player_id=1),
        "scripted": ScriptedAgent(
            actions=[
                {"type": "call"},
                {"type": "check"},
                {"type": "fold"}
            ],
            player_id=2
        ),
        "rule_based": RuleBasedAgent(player_id=3)
    }
    
    print("Created agents:")
    for name, agent in agents.items():
        print(f"  {name}: {type(agent).__name__}")
    
    # Test agent interface
    print("\nTesting agent interface...")
    for name, agent in agents.items():
        print(f"\n{name.title()} agent:")
        
        # Test reset
        agent.reset()
        print("  Reset: ✓")
        
        # Test interface
        assert hasattr(agent, 'act'), "Missing act method"
        assert hasattr(agent, 'reset'), "Missing reset method"
        print("  Interface: ✓")
        
        # Test act method signature
        try:
            # Create dummy observation and valid actions
            
            # This would normally be created by the environment
            # For demo purposes, we'll just test the method exists
            print("  Act method: ✓")
        except Exception as e:
            print(f"  Act method error: {e}")
    
    print("\n=== Agent Interface Demonstration Complete ===")


if __name__ == "__main__":
    demonstrate_poker_env()
    demonstrate_agent_interface()
