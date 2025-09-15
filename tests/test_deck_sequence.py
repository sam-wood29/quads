from unittest.mock import Mock

from quads.engine.deck_sequence import (
    build_sequence_from_hand,
    build_sequence_using_rotation,
    get_rotated_indices,
)
from quads.engine.rotation_probe import debug_rotation


def test_build_sequence_using_rotation():
    """Test deck sequence building with explicit rotation."""
    hole_cards = [
        ["As", "Kd"],  # seat 0
        ["7h", "7c"],  # seat 1
        ["Qd", "Qc"]   # seat 2
    ]
    board = ["2d", "9s", "Jh", "5c", "3d"]
    rotated_indices = [1, 2, 0]  # deal to seat 1, then 2, then 0
    
    sequence = build_sequence_using_rotation(hole_cards, board, rotated_indices)
    
    # Expected: first pass (seat 1, 2, 0), second pass (seat 1, 2, 0), then board
    expected = [
        "7h", "Qd", "As",  # first card to each seat
        "7c", "Qc", "Kd",  # second card to each seat
        "2d", "9s", "Jh", "5c", "3d"  # board
    ]
    
    assert sequence == expected


def test_build_sequence_from_hand():
    """Test deck sequence building using Hand's rotation logic."""
    # Mock Hand with players_in_button_order
    hand = Mock()
    
    # Create mock players with seat_index
    p0 = Mock()
    p0.seat_index = 0
    p0.id = 0
    
    p1 = Mock()
    p1.seat_index = 1
    p1.id = 1
    
    p2 = Mock()
    p2.seat_index = 2
    p2.id = 2
    
    # Set up button order (same as seat order for simplicity)
    hand.players_in_button_order = [p0, p1, p2]
    hand.dealer_index = 0
    
    hole_cards = [
        ["As", "Kd"],  # seat 0
        ["7h", "7c"],  # seat 1
        ["Qd", "Qc"]   # seat 2
    ]
    board = ["2d", "9s", "Jh", "5c", "3d"]
    
    sequence = build_sequence_from_hand(hand, hole_cards, board)
    
    # With dealer at seat 0, rotation should be [1, 2, 0] (left of dealer first)
    expected = [
        "7h", "Qd", "As",  # first card to each seat
        "7c", "Qc", "Kd",  # second card to each seat
        "2d", "9s", "Jh", "5c", "3d"  # board
    ]
    
    assert sequence == expected


def test_get_rotated_indices():
    """Test extracting rotated indices from Hand."""
    hand = Mock()
    
    # Create mock players
    p0 = Mock()
    p0.seat_index = 0
    p0.id = 0
    
    p1 = Mock()
    p1.seat_index = 1
    p1.id = 1
    
    p2 = Mock()
    p2.seat_index = 2
    p2.id = 2
    
    # Set up button order
    hand.players_in_button_order = [p0, p1, p2]
    hand.dealer_index = 0
    hand.players = [p0, p1, p2]
    
    rotated = get_rotated_indices(hand)
    
    # Should be [1, 2, 0] (left of dealer first)
    assert rotated == [1, 2, 0]


def test_debug_rotation():
    """Test rotation debugging helper."""
    hand = Mock()
    
    p0 = Mock()
    p0.seat_index = 0
    p0.id = 0
    
    p1 = Mock()
    p1.seat_index = 1
    p1.id = 1
    
    hand.players_in_button_order = [p0, p1]
    hand.dealer_index = 0
    hand.players = [p0, p1]
    
    debug_info = debug_rotation(hand)
    
    assert debug_info["dealer_index"] == 0
    assert debug_info["num_players"] == 2
    assert debug_info["has_players_in_button_order"] is True
    assert debug_info["button_order_ids"] == [0, 1]
    assert debug_info["button_order_seat_indices"] == [0, 1]
    assert debug_info["rotated_ids"] == [1, 0]  # left of dealer first
    assert debug_info["rotated_seat_indices"] == [1, 0]