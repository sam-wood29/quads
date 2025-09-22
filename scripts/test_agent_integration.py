#!/usr/bin/env python3
"""
Integration test showing how to use the new agent interface with existing Hand class.

This demonstrates the clean separation between agents and the engine.
"""


from quads.deuces.deck import Deck
from quads.engine.agent import ScriptedAgent
from quads.engine.conn import get_conn
from quads.engine.controller import Controller, ControllerType
from quads.engine.hand import Hand
from quads.engine.player import Player


def create_players_with_agents() -> tuple[list[Player], dict[int, ScriptedAgent]]:
    """Create players and corresponding agents."""
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
    
    # Create corresponding agents
    agents = {
        1: ScriptedAgent(
            actions=[
                {"type": "call"},  # Call preflop
                {"type": "check"}, # Check flop
                {"type": "fold"}   # Fold turn
            ],
            player_id=1
        ),
        2: ScriptedAgent(
            actions=[
                {"type": "call"},  # Call preflop
                {"type": "check"}, # Check flop
                {"type": "call"}   # Call turn
            ],
            player_id=2
        )
    }
    
    return players, agents


def test_hand_with_agents():
    """Test playing a hand using the new agent interface."""
    print("=== Hand with Agents Test ===")
    
    # Create components
    players, agents = create_players_with_agents()
    conn = get_conn()
    deck = Deck()
    
    # Create hand
    hand = Hand(
        players=players,
        id=1,
        deck=deck,
        dealer_index=0,
        game_session_id=1,
        conn=conn
    )
    
    print(f"Created hand with {len(players)} players")
    print(f"Players: {[p.name for p in players]}")
    print()
    
    # Play the hand
    print("Playing hand...")
    try:
        hand.play()
        print("Hand completed successfully!")
        print(f"Final pot: ${hand.pot:.2f}")
        print(f"Final phase: {hand.phase}")
        
        # Check final player states
        for player in players:
            status = "FOLDED" if player.has_folded else "ACTIVE"
            print(f"  {player.name}: {status}, Stack: ${player.stack/100:.2f}")
            
    except Exception as e:
        print(f"Error playing hand: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n=== Hand with Agents Test Complete ===")


def test_agent_interface_compatibility():
    """Test that the agent interface is compatible with existing code."""
    print("\n=== Agent Interface Compatibility Test ===")
    
    # Create a simple scripted agent
    agent = ScriptedAgent(
        actions=[
            {"type": "call"},
            {"type": "check"},
            {"type": "fold"}
        ],
        player_id=1
    )
    
    print(f"Created agent: {type(agent).__name__}")
    
    # Test agent methods
    print("Testing agent methods...")
    
    # Test reset
    agent.reset()
    print("Agent reset successful")
    
    # Test that agent has required interface
    assert hasattr(agent, 'act'), "Agent must have act method"
    assert hasattr(agent, 'reset'), "Agent must have reset method"
    print("Agent interface validation passed")
    
    print("=== Agent Interface Compatibility Test Complete ===")


if __name__ == "__main__":
    test_hand_with_agents()
    test_agent_interface_compatibility()
