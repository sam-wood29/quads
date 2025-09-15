import pytest

from quads.deuces.card import Card


def test_card_parsing_to_int():
    """Test that Card.new() converts card strings to integers."""
    # Test basic card conversion
    assert Card.new("As") == Card.new("As")  # Should be consistent
    assert Card.new("Kd") != Card.new("As")  # Should be different
    
    # Test that we get the expected integer representation
    as_card = Card.new("As")
    assert isinstance(as_card, int)
    assert as_card > 0


def test_card_parsing_hand_to_binary():
    """Test that Card.hand_to_binary() converts multiple cards."""
    cards = ["As", "Kd", "7h"]
    binary_cards = Card.hand_to_binary(cards)
    
    assert len(binary_cards) == 3
    assert all(isinstance(card, int) for card in binary_cards)
    assert binary_cards[0] == Card.new("As")
    assert binary_cards[1] == Card.new("Kd")
    assert binary_cards[2] == Card.new("7h")


def test_card_parsing_invalid_input():
    """Test that invalid card strings raise errors."""
    with pytest.raises(KeyError):
        Card.new("Xx")  # Invalid rank
    
    with pytest.raises(KeyError):
        Card.new("A1")  # Invalid suit 