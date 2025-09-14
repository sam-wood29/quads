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
import pprint

pp = pprint.PrettyPrinter(indent=2, width=80, depth=None, compact=False)


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
    print("=" * 60)
    print("DEBUG: Starting scripted hand run")
    print("=" * 60)
    
    # Set seed for deterministic behavior
    Deck.set_seed(42)

    # 1) DB in-memory & schema
    conn = sqlite3.connect(":memory:")
    create_schema(conn)

    # 2) Players
    start_stacks = script["start_stacks"]
    players = []
    print(f"DEBUG: Creating {len(start_stacks)} players with stacks: {start_stacks}")
    for i in range(len(start_stacks)):
        # Pass dollars directly - Player.__init__ will convert to cents
        stack_dollars = start_stacks[i]
        controller = Controller(controller_type=ControllerType.SCRIPT)
        player = Player(id=i, name=f"P{i}", controller=controller, stack=stack_dollars, seat_index=i)
        players.append(player)
        print(f"DEBUG: Created player {i}: stack={player.stack} cents (${stack_dollars})")
    
    # 3) Build deck sequence from script
    dealer_index = script["dealer_index"]
    print(f"DEBUG: Dealer index: {dealer_index}")
    
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
    print(f"DEBUG: Rotated indices: {rotated}")
    
    # Build the real deck sequence
    seq = build_sequence_using_rotation(script["hole_cards"], script["board"], rotated)
    deck = ScriptedDeck(seq)
    print(f"DEBUG: Deck sequence: {seq}")

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
    
    print(f"\n----Initial Hand State----\n")
    print(str(hand))
    print(f"\n")
    
    # Print initial player stacks
    print("DEBUG: Initial player stacks:")
    for p in hand.players:
        print(f"  Player {p.id}: {p.stack} cents (${p.stack/100:.2f})")
    
    print(f"DEBUG: Initial pot manager total: {hand.pot_manager.total_table_cents()} cents")
    print(f"DEBUG: Initial game state pot: {hand.game_state.pot} dollars")

    # 5) Play the hand - Hand does everything
    print("\n" + "=" * 60)
    print("DEBUG: Starting hand.play()")
    print("=" * 60)
    hand.play()

    # 6) Debug final state
    print("\n" + "=" * 60)
    print("DEBUG: Final hand state")
    print("=" * 60)
    
    print("DEBUG: Final player stacks:")
    for p in hand.players:
        print(f"  Player {p.id}: {p.stack} cents (${p.stack/100:.2f})")
    
    print(f"DEBUG: Final pot manager total: {hand.pot_manager.total_table_cents()} cents")
    print(f"DEBUG: Final game state pot: {hand.game_state.pot} dollars")
    print(f"DEBUG: Phase controller awarded uncontested: {hand.game_state.awarded_uncontested}")
    
    # Check if pot was properly awarded
    total_initial_stacks_cents = sum(to_cents(stack) for stack in start_stacks)
    total_final_stacks = sum(p.stack for p in hand.players)
    pot_amount = hand.pot_manager.total_table_cents()
    
    print(f"DEBUG: Total initial stacks: {total_initial_stacks_cents} cents")
    print(f"DEBUG: Total final stacks: {total_final_stacks} cents")
    print(f"DEBUG: Remaining pot: {pot_amount} cents")
    print(f"DEBUG: Money conservation check: {total_initial_stacks_cents} = {total_final_stacks + pot_amount} ? {total_initial_stacks_cents == total_final_stacks + pot_amount}")

    # 7) Return results
    cur = conn.cursor()
    cur.execute("""
        SELECT step_number, player_id, action, phase, detail, amount_to_call, highest_bet, position
        FROM actions
        WHERE hand_id=? ORDER BY step_number
    """, (hand.id,))
    actions_rows = cur.fetchall()
    
    print(f"DEBUG: Total actions logged: {len(actions_rows)}")
    
    # Calculate the actual pot amount that was awarded
    # If pot was awarded uncontested, use the game state pot (which includes uncalled bets)
    if hand.game_state.awarded_uncontested:
        # Use the game state pot which shows the total pot before uncalled bet return
        total_pot = hand.game_state.pot
    else:
        # Use pot manager total for contested pots
        total_pot = from_cents(hand.pot_manager.total_table_cents())
    
    return {
        "final_stacks": [from_cents(p.stack) for p in hand.players],
        "total_pot": total_pot,
        "actions_rows": actions_rows,
        "hand_id": hand.id,
        "game_session_id": hand.game_session_id
    }