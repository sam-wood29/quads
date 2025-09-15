import pytest

from quads.deuces.card import Card
from quads.deuces.scripted_deck import ScriptedDeck


def test_scripted_deck_draw_order():
    """Test that ScriptedDeck yields cards in exact sequence."""
    cards = ["As", "Kd", "7h", "7c", "5d"]
    deck = ScriptedDeck(cards)
    
    # Draw 2 cards
    first_two = deck.draw(2)
    assert first_two == [Card.new("As"), Card.new("Kd")]
    
    # Draw 3 more cards
    next_three = deck.draw(3)
    assert next_three == [Card.new("7h"), Card.new("7c"), Card.new("5d")]
    
    # Should be exhausted
    with pytest.raises(IndexError):
        deck.draw(1)


def test_scripted_deck_shuffle_no_op():
    """Test that shuffle() doesn't change card order."""
    cards = ["As", "Kd", "7h", "7c", "5d"]
    deck = ScriptedDeck(cards)
    
    # Draw first card
    first = deck.draw(1)
    assert first == Card.new("As")
    
    # Shuffle (should be no-op)
    deck.shuffle()
    
    # Draw next card (should be same as before shuffle)
    second = deck.draw(1)
    assert second == Card.new("Kd")


def test_scripted_deck_exhaustion_error():
    """Test proper error when deck runs out of cards."""
    cards = ["As", "Kd"]
    deck = ScriptedDeck(cards)
    
    # Draw both cards
    deck.draw(2)
    
    # Try to draw more
    with pytest.raises(IndexError, match="ScriptedDeck out of cards"):
        deck.draw(1)


def test_scripted_deck_deal_alias():
    """Test that deal() alias works the same as draw()."""
    cards = ["As", "Kd", "7h"]
    deck = ScriptedDeck(cards)
    
    # Use deal() instead of draw()
    first = deck.deal(1)
    assert first == Card.new("As")
    
    second = deck.deal(1)
    assert second == Card.new("Kd")