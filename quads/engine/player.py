import sqlite3
from enum import Enum

from quads.engine.conn import get_conn
from quads.engine.controller import Controller, ControllerType


class Player: 
    def __init__(self, id: int, name: str | None, controller: Controller, stack: float, seat_index: int):
        self.id = id
        self.name = name
        self.controller = controller
        self.stack = int(stack * 100)  # Convert to cents
        self.round_contrib = 0  # Use cents
        self.hand_contrib = 0   # Use cents
        self.current_bet = 0    # Use cents
        self.hole_cards = None
        self.has_acted = False
        self.has_folded = False
        self.all_in = False
        self.position = None
        self.seat_index = seat_index
    
    def __str__(self) -> str:
        """Comprehensive string representation for debugging."""
        # Convert cents to dollars for display
        stack_dollars = self.stack / 100.0
        hand_contrib_dollars = self.hand_contrib / 100.0
        current_bet_dollars = self.current_bet / 100.0
        
        # Format hole cards
        hole_cards_str = "None"
        if self.hole_cards:
            if isinstance(self.hole_cards, list) and len(self.hole_cards) == 2:
                try:
                    from quads.deuces.card import Card
                    cards = [Card.int_to_str(c) if isinstance(c, int) else c for c in self.hole_cards]
                    hole_cards_str = f"{cards[0]},{cards[1]}"
                except Exception:
                    hole_cards_str = str(self.hole_cards)
            else:
                hole_cards_str = str(self.hole_cards)
        
        # Status flags
        status_flags = []
        if self.has_folded:
            status_flags.append("FOLDED")
        if self.all_in:
            status_flags.append("ALL_IN")
        if self.has_acted:
            status_flags.append("ACTED")
        if hasattr(self, 'has_checked_this_round') and self.has_checked_this_round:
            status_flags.append("CHECKED")
        
        status_str = ",".join(status_flags) if status_flags else "ACTIVE"
        
        return (f"P{self.id}({self.position}, ${stack_dollars:.2f}, "
                f"bet=${current_bet_dollars:.2f}, contrib=${hand_contrib_dollars:.2f}, "
                f"cards=[{hole_cards_str}], {status_str})")
    
class Position(str, Enum):
    BUTTON = "button"
    SB = "sb"
    BB = "bb"
    UTG = "utg"
    UTG1 = "utg1"
    UTG2 = "utg2"
    LJ = "lj"
    MP = "mp"
    HJ = "hj"
    CO = "co"

    def __str__(self):
        return self.name.replace("UTG1", "UTG+1").replace("UTG2", "UTG+2")
    
POSITIONS_BY_PLAYER_COUNT = {
    2: [Position.SB, Position.BB],  # In heads-up, dealer is SB
    3: [Position.BUTTON, Position.SB, Position.BB],
    4: [Position.BUTTON, Position.SB, Position.BB, Position.UTG],
    5: [Position.BUTTON, Position.SB, Position.BB, Position.UTG, Position.CO],
    6: [Position.BUTTON, Position.SB, Position.BB, Position.UTG, Position.HJ, Position.CO],
    7: [Position.BUTTON, Position.SB, Position.BB, Position.UTG, Position.MP, Position.HJ, Position.CO],
    8: [Position.BUTTON, Position.SB, Position.BB, Position.UTG, Position.UTG1, Position.MP, Position.HJ, Position.CO],
    9: [Position.BUTTON, Position.SB, Position.BB, Position.UTG, Position.UTG1, Position.UTG2, Position.MP, Position.HJ, Position.CO],
    10:[Position.BUTTON, Position.SB, Position.BB, Position.UTG, Position.UTG1, Position.UTG2, Position.MP, Position.LJ, Position.HJ, Position.CO],
}
    
def create_load_player_from_script(player_data: list, same_stack: bool, stack_amount: float) -> list[Player]:
    if not same_stack:
        raise RuntimeError("Different starting stacks not implemented.")
    existing_players = [p for p in player_data if p.get("status") == "exists"]
    new_players = [p for p in player_data if p.get("status" == "new")]
    existing_players_validated = validate_existing_players_from_script(existing_players)
    new_players_validated = validate_new_players_from_script(new_players)
    if existing_players_validated and new_players_validated:
        game_player_list = []
        if len(existing_players) > 0:
            existing_player_objs_list = load_existing_players_by_id(player_list=existing_players, same_stack=same_stack, stack_amount=stack_amount, is_script=True)
            game_player_list.extend(existing_player_objs_list)
        if len(new_players) > 0:
            raise RuntimeError("Loading new players is not implemented yet.")
        return game_player_list
            
        
def validate_existing_players_from_script(existing_players: list) -> bool:
    seen_ids = set()
    for p in existing_players:
        pid = p["id"]
        if pid in seen_ids:
            raise ValueError("Duplicate player ID found in existing players.")
        seen_ids.add(pid)
    return True, seen_ids


def validate_new_players_from_script(new_players: list) -> bool:
    if len(new_players) > 0:
        raise RuntimeError("No implementation for loading in 'new' players.")
    return True


def load_existing_players_by_id(player_list: list, same_stack: bool, stack_amount: float, is_script: bool, conn: sqlite3.Connection=get_conn()) -> list[Player]:
    ids = []
    for p in player_list:
        pid = p["id"]
        ids.append(pid)
    cursor = conn.cursor()
    placeholder_ids = ",".join(["?"] * len(ids))
    query = f"SELECT id, name FROM players WHERE id IN ({placeholder_ids})"
    cursor.execute(query, ids)
    rows = cursor.fetchall()
    conn.close()
    if is_script:
        controller = Controller(controller_type=ControllerType.SCRIPT)
    else:
        raise RuntimeError("Non Scripted play not implemented.")
    if same_stack:
        players = []
        for i, row in enumerate(rows):
            player = Player(id=row[0], name=row[1], stack=stack_amount, controller=controller, seat_index=i)
            players.append(player)
    else:
        raise RuntimeError("Different starting stacks not implemented.")
    return players