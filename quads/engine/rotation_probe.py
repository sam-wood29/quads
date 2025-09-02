def get_rotated_indices(hand) -> list[int]:
    """
    Extract rotated indices from Hand's dealing logic.
    
    Args:
        hand: Hand instance
        
    Returns:
        List of seat indices in deal order
    """
    # 1) Preferred: hand.players_in_button_order contains Player with seat_index
    if hasattr(hand, "players_in_button_order"):
        players = hand.players_in_button_order
        if players and hasattr(players[0], "seat_index"):
            # Apply the same rotation logic as _deal_hole_cards()
            n = 1 % len(players)
            rotated_players = players[n:] + players[:n]
            return [p.seat_index for p in rotated_players]
    
    # 2) Fallback: use player IDs if seat_index not available
    if hasattr(hand, "players_in_button_order"):
        players = hand.players_in_button_order
        if players and hasattr(players[0], "id"):
            n = 1 % len(players)
            rotated_players = players[n:] + players[:n]
            return [p.id for p in rotated_players]
    
    # 3) Generic fallback: start left of dealer and wrap (SB, BB, ... dealer)
    n = len(hand.players)
    start = (hand.dealer_index + 1) % n
    return [(start + i) % n for i in range(n)]


def debug_rotation(hand) -> dict:
    """
    Debug helper to understand Hand's rotation logic.
    
    Args:
        hand: Hand instance
        
    Returns:
        Dict with rotation information
    """
    info = {
        "dealer_index": getattr(hand, "dealer_index", None),
        "num_players": len(hand.players),
        "has_players_in_button_order": hasattr(hand, "players_in_button_order"),
    }
    
    if hasattr(hand, "players_in_button_order"):
        players = hand.players_in_button_order
        info["button_order_ids"] = [p.id for p in players] if players else []
        info["button_order_seat_indices"] = [p.seat_index for p in players] if players and hasattr(players[0], "seat_index") else []
        
        # Calculate rotation
        n = 1 % len(players) if players else 0
        rotated_players = players[n:] + players[:n] if players else []
        info["rotated_ids"] = [p.id for p in rotated_players]
        info["rotated_seat_indices"] = [p.seat_index for p in rotated_players] if rotated_players and hasattr(rotated_players[0], "seat_index") else []
    
    return info