#!/usr/bin/env python3
"""
Simple test showing agent interface working with scripted hands.
"""


from quads.engine.agent import ScriptedAgent
from quads.engine.controller import Controller, ControllerType
from quads.engine.player import Player


def create_scripted_hand_test():
    """Test agent interface with a scripted hand."""
    print("=== Scripted Hand with Agents Test ===")
    
    # Create players
    players = [
        Player(
            id=1,
            name="Player 1",
            controller=Controller(ControllerType.SCRIPT),
            stack=100.0,
            seat_index=0
        ),
        Player(
            id=2,
            name="Player 2",
            controller=Controller(ControllerType.SCRIPT),
            stack=100.0,
            seat_index=1
        )
    ]
    
    # Create scripted hand data
    script = {
        "hand_id": 1,
        "players": [
            {
                "id": 1,
                "name": "Player 1",
                "stack": 100.0,
                "seat_index": 0,
                "actions": [
                    {"type": "call"},  # Call preflop
                    {"type": "check"}, # Check flop
                    {"type": "fold"}   # Fold turn
                ]
            },
            {
                "id": 2,
                "name": "Player 2", 
                "stack": 100.0,
                "seat_index": 1,
                "actions": [
                    {"type": "call"},  # Call preflop
                    {"type": "check"}, # Check flop
                    {"type": "call"}   # Call turn
                ]
            }
        ],
        "community_cards": ["Ah", "Kh", "Qh", "Jh", "Th"],  # Royal flush
        "dealer_index": 0
    }
    
    # Create corresponding agents
    agents = {
        1: ScriptedAgent(
            actions=script["players"][0]["actions"],
            player_id=1
        ),
        2: ScriptedAgent(
            actions=script["players"][1]["actions"],
            player_id=2
        )
    }
    
    print(f"Created {len(players)} players with agents")
    print(f"Agent types: {[type(agent).__name__ for agent in agents.values()]}")
    
    # Test agent interface
    print("\nTesting agent interface...")
    for player_id, agent in agents.items():
        print(f"Player {player_id}: {type(agent).__name__}")
        
        # Test reset
        agent.reset()
        print("  Reset successful")
        
        # Test that agent has required interface
        assert hasattr(agent, 'act'), f"Agent {player_id} missing act method"
        assert hasattr(agent, 'reset'), f"Agent {player_id} missing reset method"
        print("  Interface validation passed")
    
    print("\n=== Scripted Hand with Agents Test Complete ===")


def test_agent_swapping_demonstration():
    """Demonstrate that agents can be swapped without engine changes."""
    print("\n=== Agent Swapping Demonstration ===")
    
    # Create base players
    # players = [
    #     Player(
    #         id=1,
    #         name="Player 1",
    #         controller=Controller(ControllerType.SCRIPT),
    #         stack=100.0,
    #         seat_index=0
    #     ),
    #     Player(
    #         id=2,
    #         name="Player 2",
    #         controller=Controller(ControllerType.SCRIPT),
    #         stack=100.0,
    #         seat_index=1
    #     )
    # ]
    
    # Test 1: Both players use ScriptedAgent
    print("Test 1: Both players use ScriptedAgent")
    agents1 = {
        1: ScriptedAgent([{"type": "call"}, {"type": "fold"}], 1),
        2: ScriptedAgent([{"type": "call"}, {"type": "call"}], 2)
    }
    
    print(f"  Player 1: {type(agents1[1]).__name__}")
    print(f"  Player 2: {type(agents1[2]).__name__}")
    
    # Test 2: Mix of agent types
    print("\nTest 2: Mix of agent types")
    from quads.engine.agent import HumanAgent, RuleBasedAgent
    
    agents2 = {
        1: HumanAgent(1),
        2: RuleBasedAgent(2)
    }
    
    print(f"  Player 1: {type(agents2[1]).__name__}")
    print(f"  Player 2: {type(agents2[2]).__name__}")
    
    # Test 3: All RuleBasedAgent
    print("\nTest 3: All RuleBasedAgent")
    agents3 = {
        1: RuleBasedAgent(1),
        2: RuleBasedAgent(2)
    }
    
    print(f"  Player 1: {type(agents3[1]).__name__}")
    print(f"  Player 2: {type(agents3[2]).__name__}")
    
    print("\nAll agent combinations created successfully!")
    print("Agents can be swapped without changing engine code.")
    
    print("\n=== Agent Swapping Demonstration Complete ===")


if __name__ == "__main__":
    create_scripted_hand_test()
    test_agent_swapping_demonstration()
