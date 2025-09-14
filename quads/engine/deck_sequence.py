from typing import List


def build_sequence_using_rotation(hole_cards: List[List[str]], board: List[str], rotated_indices: List[int]) -> List[str]:
    """
    Build deck sequence that matches Hand._deal_hole_cards() rotation order.
    
    Args:
        hole_cards: List of [card1, card2] for each seat (hole_cards[i] belongs to seat i)
        board: List of 5 community cards [flop1, flop2, flop3, turn, river]
        rotated_indices: Deal order indices from Hand (rotated_players order)
        
    Returns:
        List of card strings in exact draw order for ScriptedDeck
    """
    n = len(rotated_indices)
    seq: list[str] = []
    
    # First pass: deal first card to each player in rotation order
    for seat in rotated_indices:
        seq.append(hole_cards[seat][0])
    
    # Second pass: deal second card to each player in rotation order
    for seat in rotated_indices:
        seq.append(hole_cards[seat][1])
    
    # Board: flop (3), turn (1), river (1)
    seq.extend(board)
    
    return seq


def build_sequence_from_hand(hand, hole_cards: List[List[str]], board: List[str]) -> List[str]:
    """
    Build deck sequence using Hand's actual rotation logic.
    
    Args:
        hand: Hand instance with players_in_button_order
        hole_cards: List of [card1, card2] for each seat
        board: List of 5 community cards
        
    Returns:
        List of card strings in exact draw order
    """
    rotated_indices = get_rotated_indices(hand)
    return build_sequence_using_rotation(hole_cards, board, rotated_indices)


def get_rotated_indices(hand) -> list[int]:
    """
    Extract the rotated indices from Hand's dealing logic.
    
    Args:
        hand: Hand instance
        
    Returns:
        List of seat indices in deal order
    """
    # Method 1: Use players_in_button_order if available
    if hasattr(hand, "players_in_button_order") and hand.players_in_button_order:
        print("Getting players in button order.")
        players = hand.players_in_button_order
        # Apply the same rotation logic as _deal_hole_cards()
        n = 1 % len(players)  # This is the rotation offset
        rotated_players = players[n:] + players[:n]
        
        # Extract seat indices from rotated players
        if hasattr(rotated_players[0], "seat_index"):
            return [p.seat_index for p in rotated_players]
        elif hasattr(rotated_players[0], "id"):
            # Fallback: use player IDs if seat_index not available
            return [p.id for p in rotated_players]
    
    # Method 2: Generic fallback - start left of dealer and wrap
    n = len(hand.players)
    start = (hand.dealer_index + 1) % n
    return [(start + i) % n for i in range(n)]