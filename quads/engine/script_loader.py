import json
from pathlib import Path
from typing import Any


def load_script(path: str | Path) -> dict[str, Any]:
    """
    Load and normalize a script file.
    
    Args:
        path: Path to JSON script file
        
    Returns:
        Normalized script dict with consistent key types
    """
    with open(Path(path)) as f:
        raw = json.load(f)
    return _normalize_keys(raw)


def _normalize_keys(script: dict) -> dict:
    """
    Normalize script keys to handle both string and integer seat indices.
    
    Args:
        script: Raw script dict from JSON
        
    Returns:
        Normalized script with consistent key types
    """
    def norm_phase(phase_dict: dict | None):
        """Normalize phase actions to use integer keys."""
        if not phase_dict:
            return {"actions": {}}
        
        acts = phase_dict.get("actions", {})
        norm = {}
        
        for k, v in acts.items():
            # Accept "0" or 0; store as int keys internally
            norm[int(k)] = v
        
        return {"actions": norm}
    
    # Create normalized copy
    out = dict(script)
    
    # Normalize all phase sections
    for ph in ("preflop", "flop", "turn", "river"):
        out[ph] = norm_phase(script.get(ph))
    
    return out


def get_script_actions_by_seat(script: dict) -> dict[int, list[dict]]:
    """
    Extract all actions for each seat from normalized script.
    
    Args:
        script: Normalized script dict
        
    Returns:
        Dict mapping seat index to list of actions
    """
    actions_by_seat = {}
    
    # Process each phase
    for phase in ("preflop", "flop", "turn", "river"):
        phase_actions = script.get(phase, {}).get("actions", {})
        
        for seat_idx, actions in phase_actions.items():
            if seat_idx not in actions_by_seat:
                actions_by_seat[seat_idx] = []
            
            # Add actions for this seat in this phase
            actions_by_seat[seat_idx].extend(actions)
    
    return actions_by_seat


def validate_script_structure(script: dict) -> bool:
    """
    Validate that script has required fields.
    
    Args:
        script: Script dict to validate
        
    Returns:
        True if valid, raises ValueError if invalid
    """
    required_fields = ["small_blind", "big_blind", "start_stacks", "dealer_index", "hole_cards", "board"]
    
    for field in required_fields:
        if field not in script:
            raise ValueError(f"Script missing required field: {field}")
    
    # Validate hole_cards structure
    hole_cards = script["hole_cards"]
    if not isinstance(hole_cards, list):
        raise ValueError("hole_cards must be a list")
    
    for i, cards in enumerate(hole_cards):
        if not isinstance(cards, list) or len(cards) != 2:
            raise ValueError(f"hole_cards[{i}] must be a list of 2 cards")
    
    # Validate board structure
    board = script["board"]
    if not isinstance(board, list) or len(board) != 5:
        raise ValueError("board must be a list of 5 cards")
    
    # Validate start_stacks
    start_stacks = script["start_stacks"]
    if not isinstance(start_stacks, list):
        raise ValueError("start_stacks must be a list")
    
    if len(start_stacks) != len(hole_cards):
        raise ValueError("start_stacks and hole_cards must have same length")
    
    return True