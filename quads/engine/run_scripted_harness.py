import sqlite3
from typing import Any, List
from quads.deuces.scripted_deck import ScriptedDeck
from quads.engine.player import Player
from quads.engine.hand import Hand
from quads.engine.scripted_agent import ScriptedAgent
from quads.engine.deck_sequence import get_rotated_indices, build_sequence_using_rotation
from quads.engine.script_loader import get_script_actions_by_seat
from quads.engine.va_factory import make_va_factory
from quads.engine.money import to_cents
from quads.deuces.deck import Deck


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
    """
    Run a scripted hand end-to-end.
    
    Args:
        script: Normalized script dict
        
    Returns:
        Dict with final_stacks, total_pot, and actions_rows
    """
    # Set seed for deterministic behavior
    Deck.set_seed(42)

    # 1) DB in-memory & schema
    conn = sqlite3.connect(":memory:")
    create_schema(conn)

    # 2) Players
    start_stacks = script["start_stacks"]
    players = []
    for i in range(len(start_stacks)):
        # Convert stack to cents
        stack_cents = to_cents(start_stacks[i])
        player = Player(
            id=i, 
            name=f"P{i}", 
            controller=None,  # Will be handled by script
            stack=stack_cents,
            seat_index=i
        )
        players.append(player)
    
    dealer_index = script["dealer_index"]

    # 3) Create a "probe" Hand to compute rotated order before building deck sequence
    probe_deck = ScriptedDeck(["As", "Ad"] * 20)  # harmless filler
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

    # 4) Build the real deck sequence to match rotated order
    seq = build_sequence_using_rotation(script["hole_cards"], script["board"], rotated)
    deck = ScriptedDeck(seq)

    # 5) Re-create Hand with the real deck
    hand = Hand(
        players=players, 
        id=1, 
        deck=deck, 
        dealer_index=dealer_index,
        game_session_id=1, 
        conn=conn,
        small_blind=script["small_blind"],
        big_blind=script["big_blind"]
    )

    # 6) Assemble per-seat action streams using normalized keys
    actions_by_seat = get_script_actions_by_seat(script)

    # 7) Create agents with validation factory
    va_factory = make_va_factory(hand)
    agents = []
    for seat_idx in range(len(players)):
        actions = actions_by_seat.get(seat_idx, [])
        agent = ScriptedAgent(actions, va_factory)
        agents.append(agent)

    # 8) Play the hand using existing logic but with agent decisions
    result = play_hand_with_agents(hand, agents, script)

    # 9) Extract ordered action rows & outputs
    cur = conn.cursor()
    cur.execute("""
        SELECT step_number, player_id, action, phase, detail, amount_to_call, highest_bet, position
        FROM actions
        WHERE hand_id=? ORDER BY step_number
    """, (hand.id,))
    ordered_rows = cur.fetchall()

    # Convert final stacks back to dollars for output
    final_stacks = [p.stack / 100.0 for p in hand.players]  # Convert cents back to dollars
    total_pot = hand.pot

    return {
        "final_stacks": final_stacks, 
        "total_pot": total_pot, 
        "actions_rows": ordered_rows
    }


def play_hand_with_agents(hand: Hand, agents: List[ScriptedAgent], script: dict):
    """
    Play a hand using scripted agents for decisions.
    
    Args:
        hand: Hand instance
        agents: List of ScriptedAgent instances, one per seat
        script: Script dict for community card dealing
        
    Returns:
        Result dict
    """
    # Override the _get_player_action method to use agents
    original_get_player_action = hand._get_player_action
    
    def agent_get_player_action(acting_player: Player, game_state):
        """Get action from agent instead of script."""
        seat_idx = acting_player.id
        if seat_idx >= len(agents):
            raise RuntimeError(f"No agent for seat {seat_idx}")
        
        agent = agents[seat_idx]
        validated_action = agent.decide(acting_player, game_state)
        
        # Convert ValidatedAction back to the format expected by existing code
        return validated_action.action_type, validated_action.amount, 0  # amount_to_call not used
    
    # Override community card dealing to use our script
    original_deal_community_cards = hand._deal_community_cards
    
    def scripted_deal_community_cards():
        """Deal community cards from our script."""
        # Extract community cards from script based on current phase
        if hand.phase.value == "flop":
            return [hand.deck.draw() for _ in range(3)]  # Draw 3 cards for flop
        elif hand.phase.value in ["turn", "river"]:
            return [hand.deck.draw()]  # Draw 1 card for turn/river
        else:
            raise ValueError(f"Unexpected phase for community deal: {hand.phase}")
    
    # Replace the methods temporarily
    hand._get_player_action = agent_get_player_action
    hand._deal_community_cards = scripted_deal_community_cards
    
    try:
        # Play the hand using existing logic
        result = hand.play()
        return {"success": True, "result": result}
    finally:
        # Restore original methods
        hand._get_player_action = original_get_player_action
        hand._deal_community_cards = original_deal_community_cards