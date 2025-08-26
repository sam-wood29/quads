import pytest

from quads.engine.hand import Hand, Phase


def test_community_cards_methods_directly():
    """Test community card methods without full hand setup"""
    
    # Create a minimal hand object
    hand = Hand.__new__(Hand)  # Create without calling __init__
    
    # Set up minimal attributes needed for testing
    hand.community_cards = []
    hand.script = [
        {"type": "deal_community", "cards": ["Ah", "Kh", "Qh"]},  # Flop
        {"type": "deal_community", "cards": ["Jh"]},               # Turn
        {"type": "deal_community", "cards": ["Th"]},               # River
    ]
    hand.script_index = 0
    
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
    hand._apply_community_deal(Phase.TURN)
    print(f"After turn: {hand.community_cards}")
    print(f"Length: {len(hand.community_cards)}")
    
    assert len(hand.community_cards) == 4, f"After turn should have 4 cards, got {len(hand.community_cards)}"
    
    # Test RIVER
    print("\n--- Testing RIVER ---")
    hand._apply_community_deal(Phase.RIVER)
    print(f"After river: {hand.community_cards}")
    print(f"Length: {len(hand.community_cards)}")
    
    assert len(hand.community_cards) == 5, f"After river should have 5 cards, got {len(hand.community_cards)}"
    
    # Verify all cards are Deuces ints
    assert all(isinstance(c, int) for c in hand.community_cards), "All cards should be Deuces ints"
    
    print("✅ All community card tests passed!")

def test_community_cards_single_source_of_truth():
    """Test that community_cards list is the single source of truth"""
    
    # Create a minimal hand object with proper initialization
    from unittest.mock import Mock

    
    hand = Hand.__new__(Hand)
    hand.community_cards = []
    hand.script = [
        {"type": "deal_community", "cards": ["Ah", "Kh", "Qh"]},  # Flop
        {"type": "deal_community", "cards": ["Jh"]},               # Turn
        {"type": "deal_community", "cards": ["Th"]},               # River
    ]
    hand.script_index = 0
    
    # Create a minimal game_state to avoid AttributeError
    hand.game_state = Mock()
    hand.game_state.phase = Phase.DEAL.value
    
    # Verify initial state
    assert hand.community_cards == [], "Community cards should start empty"
    assert isinstance(hand.community_cards, list), "Community cards should be a list"
    
    # Test that the list grows correctly
    hand.phase = Phase.FLOP
    hand._apply_community_deal(Phase.FLOP)
    assert len(hand.community_cards) == 3, "Flop should add exactly 3 cards"
    
    hand.phase = Phase.TURN
    hand._apply_community_deal(Phase.TURN)
    assert len(hand.community_cards) == 4, "Turn should add exactly 1 card"
    
    hand.phase = Phase.RIVER
    hand._apply_community_deal(Phase.RIVER)
    assert len(hand.community_cards) == 5, "River should add exactly 1 card"
    
    # Verify all cards are Deuces ints
    for card in hand.community_cards:
        assert isinstance(card, int), f"Card {card} should be a Deuces int"
        assert card > 0, f"Card {card} should be a positive integer"
    
    print("✅ Single source of truth test passed!")

def test_no_reparsing_of_cards():
    """Test that cards are not re-parsed when evaluating hands"""
    
    # Create a minimal hand object with proper initialization
    from unittest.mock import Mock
    
    hand = Hand.__new__(Hand)
    hand.community_cards = []
    hand.script = [
        {"type": "deal_community", "cards": ["Ah", "Kh", "Qh"]},  # Flop
        {"type": "deal_community", "cards": ["Jh"]},               # Turn
        {"type": "deal_community", "cards": ["Th"]},               # River
    ]
    hand.script_index = 0
    
    # Create a minimal game_state to avoid AttributeError
    hand.game_state = Mock()
    hand.game_state.phase = Phase.DEAL.value
    
    # Deal community cards
    hand.phase = Phase.FLOP
    hand._apply_community_deal(Phase.FLOP)
    
    # Store the original card objects
    original_cards = hand.community_cards.copy()
    
    # Test evaluation - should use the same card objects
    # Create mock hole cards for testing
    hole_cards_str = "As,Ad"  # Mock hole cards
    
    # This should use hand.community_cards directly (no re-parsing)
    score, hand_class = hand._get_score(hole_cards_str, "")
    
    # Verify the community cards list wasn't modified
    assert hand.community_cards == original_cards, "Community cards should not be modified during evaluation"
    assert all(card is original_cards[i] for i, card in enumerate(hand.community_cards)), "Should use same card objects"
    
    print("✅ No re-parsing test passed!")

def test_logging_conversion():
    """Test that logging converts to strings only when needed"""
    
    # Create a minimal hand object
    hand = Hand.__new__(Hand)
    hand.community_cards = []
    hand.script = [
        {"type": "deal_community", "cards": ["Ah", "Kh", "Qh"]},  # Flop
        {"type": "deal_community", "cards": ["Jh"]},               # Turn
        {"type": "deal_community", "cards": ["Th"]},               # River
    ]
    hand.script_index = 0
    
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