from unittest.mock import Mock

import pytest

from quads.engine.hand import Hand, Phase


def test_community_cards_methods_directly():
    """Test community card methods without full hand setup"""
    
    # Create a minimal hand object
    hand = Hand.__new__(Hand)  # Create without calling __init__
    
    # Set up minimal attributes needed for testing
    hand.community_cards = []
    hand.script = {
        "board": ["Ah", "Kh", "Qh", "Jh", "Th"]  # New structured format
    }
    
    # Create a minimal game_state to avoid AttributeError
    hand.conn = Mock()
    hand.game_session_id = 1
    hand.id = 1
    
    hand.game_state = Mock()
    hand.game_state.phase = Phase.FLOP.value
    hand.game_state.next_step_number = Mock(return_value=1)
    
    # Test the community card methods directly
    print("=== Testing Community Card Methods ===")
    
    # Test FLOP
    print("\n--- Testing FLOP ---")
    hand._apply_community_deal(Phase.FLOP)
    print(f"After flop: {hand.community_cards}")
    print(f"Length: {len(hand.community_cards)}")
    print(f"All ints: {all(isinstance(c, int) for c in hand.community_cards)}")
    
    assert len(hand.community_cards) == 3, f"Flop should have 3 cards, got {len(hand.community_cards)}"
    assert all(isinstance(c, int) for c in hand.community_cards), "All flop cards should be Deuces ints"
    
    # Test TURN
    print("\n--- Testing TURN ---")
    hand.game_state.phase = Phase.TURN.value  # Set to TURN phase
    hand._apply_community_deal(Phase.TURN)
    print(f"After turn: {hand.community_cards}")
    print(f"Length: {len(hand.community_cards)}")
    
    assert len(hand.community_cards) == 4, f"After turn should have 4 cards, got {len(hand.community_cards)}"
    
    # Test RIVER
    print("\n--- Testing RIVER ---")
    hand.game_state.phase = Phase.RIVER.value  # Set to RIVER phase
    hand._apply_community_deal(Phase.RIVER)
    print(f"After river: {hand.community_cards}")
    print(f"Length: {len(hand.community_cards)}")
    
    assert len(hand.community_cards) == 5, f"After river should have 5 cards, got {len(hand.community_cards)}"
    
    # Verify all cards are Deuces ints
    assert all(isinstance(c, int) for c in hand.community_cards), "All cards should be Deuces ints"
    
    print("✅ All community card tests passed!")

def test_logging_conversion():
    """Test that logging converts to strings only when needed"""
    
    # Create a minimal hand object
    hand = Hand.__new__(Hand)
    hand.community_cards = []
    hand.script = {
        "board": ["Ah", "Kh", "Qh", "Jh", "Th"]  # New structured format
    }
    
    # Mock the attributes that log_action_needs
    hand.conn = Mock()
    hand.game_session_id = 1
    hand.id = 1
    
    # Create a minimal game_state to avoid Attribute Error
    hand.game_state = Mock()
    hand.game_state.phase = Phase.DEAL.value
    hand.game_state.next_step_number = Mock(return_value=1)
    
    # Deal all community cards
    hand._apply_community_deal(Phase.FLOP)
    hand._apply_community_deal(Phase.TURN)
    hand._apply_community_deal(Phase.RIVER)
    
    # Test logging conversion (strings only when needed)
    print("\n=== Testing Logging Conversion ===")
    community_cards_str = hand._get_community_cards(Phase.RIVER)
    print(f"Community cards for logging: {community_cards_str}")
    print(f"Type: {type(community_cards_str)}")
    
    # Verify logging gets strings, but authoritative list remains ints
    assert isinstance(community_cards_str, str), "Logging should get string representation"
    assert all(isinstance(c, int) for c in hand.community_cards), "Authoritative list should remain ints"
    
    # Verify the string contains the right cards
    expected_cards = ["Ah", "Kh", "Qh", "Jh", "Th"]
    for expected in expected_cards:
        assert expected in community_cards_str, f"Expected {expected} in logged string"
    
    print("✅ Logging conversion test passed!")

if __name__ == "__main__":
    # For running directly (not through pytest)
    pytest.main([__file__, "-v", "-s"])