import sqlite3
from typing import Any, List
from quads.deuces.scripted_deck import ScriptedDeck
from quads.engine.player import Player
from quads.engine.hand import Hand
from quads.engine.scripted_agent import ScriptedAgent
from quads.engine.deck_sequence import get_rotated_indices, build_sequence_using_rotation
from quads.engine.script_loader import get_script_actions_by_seat
from quads.engine.va_factory import make_va_factory
from quads.engine.money import to_cents, from_cents
from quads.deuces.deck import Deck
from quads.engine.controller import Controller, ControllerType
from quads.engine.hand import Phase, Position, BettingOrder, ActionType
from quads.engine.hand import log_action


def create_schema(conn: sqlite3.Connection):
    """Create minimal schema for testing."""
    cursor = conn.cursor()
    
    # Create game_sessions table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS game_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            object_game_type TEXT,
            small_blind REAL,
            big_blind REAL,
            same_stack BOOLEAN,
            rebuy_setting TEXT,
            stack_amount REAL,
            script_name TEXT
        )
    """)
    
    # Create actions table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_session_id INTEGER NOT NULL,
            hand_id INTEGER NOT NULL,
            step_number INTEGER NOT NULL,
            player_id INTEGER,
            position TEXT,
            phase TEXT,
            action TEXT NOT NULL,
            amount REAL,
            hole_cards TEXT,
            hole_card1 TEXT,
            hole_card2 TEXT,
            community_cards TEXT,
            hand_rank_5 INTEGER,
            hand_class TEXT,
            pf_hand_class TEXT,
            high_rank INTEGER,
            low_rank INTEGER,
            is_pair BOOLEAN,
            is_suited BOOLEAN,
            gap INTEGER,
            chen_score REAL,
            amount_to_call REAL,
            percent_stack_to_call REAL,
            highest_bet REAL,
            pot_odds REAL,
            detail TEXT
        )
    """)
    
    conn.commit()


def run_script(script: dict[str, Any]):
    """Run a complete scripted poker hand."""
    # Set seed for deterministic behavior
    Deck.set_seed(42)

    # 1) DB in-memory & schema
    conn = sqlite3.connect(":memory:")
    create_schema(conn)

    # 2) Players
    start_stacks = script["start_stacks"]
    players = []
    for i in range(len(start_stacks)):
        # Line 85: Remove to_cents conversion since script already has cents
        stack_cents = start_stacks[i]  # Direct assignment
        controller = Controller(controller_type=ControllerType.SCRIPT)
        player = Player(id=i, name=f"P{i}", controller=controller, stack=stack_cents, seat_index=i)
        players.append(player)
    
    # 3) Build deck sequence from script
    dealer_index = script["dealer_index"]
    
    # Create a probe hand to get rotation
    probe_deck = ScriptedDeck(["As", "Ad"] * 20)
    probe_hand = Hand(
        players=players, 
        id=1, 
        deck=probe_deck, 
        dealer_index=dealer_index,
        game_session_id=1, 
        conn=conn,
        small_blind=script["small_blind"],
        big_blind=script["big_blind"]
    )
    rotated = get_rotated_indices(probe_hand)
    
    # Build the real deck sequence
    seq = build_sequence_using_rotation(script["hole_cards"], script["board"], rotated)
    deck = ScriptedDeck(seq)

    # 4) Create Hand with script - Hand handles everything
    hand = Hand(
        players=players, 
        id=1, 
        deck=deck,
        dealer_index=dealer_index,
        game_session_id=1, 
        conn=conn,
        script=script,  # Hand processes this
        small_blind=script["small_blind"],
        big_blind=script["big_blind"]
    )

    # 5) Play the hand - Hand does everything
    hand.play()

    # 6) Return results
    cur = conn.cursor()
    cur.execute("""
        SELECT step_number, player_id, action, phase, detail, amount_to_call, highest_bet, position
        FROM actions
        WHERE hand_id=? ORDER BY step_number
    """, (hand.id,))
    actions_rows = cur.fetchall()
    
    return {
        "final_stacks": [from_cents(p.stack) for p in hand.players],
        "total_pot": from_cents(hand.pot_manager.total_table_cents()),
        "actions_rows": actions_rows,
        "hand_id": hand.id,
        "game_session_id": hand.game_session_id
    }