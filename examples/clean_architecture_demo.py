"""
Example demonstrating the new clean separation architecture.

This shows how RulesEngine, ActionLogger, and Hand orchestration work together.
"""

import sqlite3

from quads.engine.action_data import ActionDecision, GameStateSnapshot, LogContext
from quads.engine.action_logger import ActionLogger
from quads.engine.enums import ActionType, Phase
from quads.engine.money import to_cents
from quads.engine.rules_engine import RulesEngine


def demonstrate_clean_architecture():
    """
    Demonstrate the clean separation of rules, logging, and orchestration.
    """
    print("=== Clean Architecture Demo ===\n")
    
    # 1. Create the components
    rules_engine = RulesEngine(small_blind=0.25, big_blind=0.50)
    
    # Create a simple in-memory database for demo
    conn = sqlite3.connect(':memory:')
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE actions (
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
            is_pair INTEGER,
            is_suited INTEGER,
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
    
    action_logger = ActionLogger(conn)
    
    # 2. Create a simple game state
    game_state = GameStateSnapshot(
        hand_id=1,
        phase=Phase.PREFLOP,
        pot_cents=to_cents(0.75),  # SB + BB
        community_cards=[],
        players=[
            {
                'id': 0,
                'name': 'Player 0',
                'stack': to_cents(100.0),
                'current_bet': to_cents(0.25),  # SB
                'hand_contrib': to_cents(0.25),
                'round_contrib': to_cents(0.25),
                'has_folded': False,
                'is_all_in': False,
                'position': 'sb'
            },
            {
                'id': 1,
                'name': 'Player 1',
                'stack': to_cents(100.0),
                'current_bet': to_cents(0.50),  # BB
                'hand_contrib': to_cents(0.50),
                'round_contrib': to_cents(0.50),
                'has_folded': False,
                'is_all_in': False,
                'position': 'bb'
            }
        ],
        highest_bet=to_cents(0.50),
        last_raise_increment=to_cents(0.50),
        last_aggressor_seat=1,  # BB
        street_number=1,
        acted_this_round={0: False, 1: False},
        committed_this_round={0: to_cents(0.25), 1: to_cents(0.50)}
    )
    
    print("Initial game state:")
    print(f"  Pot: ${game_state.pot_cents / 100:.2f}")
    print(f"  Player 0: ${game_state.players[0]['stack'] / 100:.2f} stack, ${game_state.players[0]['current_bet'] / 100:.2f} bet")
    print(f"  Player 1: ${game_state.players[1]['stack'] / 100:.2f} stack, ${game_state.players[1]['current_bet'] / 100:.2f} bet")
    print()
    
    # 3. Get valid actions for Player 0 (SB)
    print("Step 1: Get valid actions for Player 0 (SB)")
    valid_actions = rules_engine.get_valid_actions(game_state, 0)
    print(f"  Valid actions: {[action.value for action in valid_actions.actions]}")
    print(f"  Amount to call: ${valid_actions.amount_to_call / 100:.2f}")
    print(f"  Can raise: {valid_actions.can_raise}")
    print()
    
    # 4. Player 0 decides to call
    print("Step 2: Player 0 decides to call")
    decision = ActionDecision(
        player_id=0,
        action_type=ActionType.CALL,
        amount=to_cents(0.25)
    )
    
    # 5. Apply the action (pure rules logic)
    print("Step 3: Apply action using RulesEngine")
    new_state, applied_action = rules_engine.apply_action(game_state, decision)
    
    print(f"  Action applied: {applied_action.action_type.value} ${applied_action.amount / 100:.2f}")
    print(f"  New pot: ${new_state.pot_cents / 100:.2f}")
    print(f"  Player 0 new stack: ${new_state.players[0]['stack'] / 100:.2f}")
    print(f"  Player 0 new bet: ${new_state.players[0]['current_bet'] / 100:.2f}")
    print()
    
    # 6. Log the action (side effects)
    print("Step 4: Log action using ActionLogger")
    log_context = LogContext(
        hand_id=1,
        game_session_id=1,
        step_number=1,
        phase=Phase.PREFLOP,
        position='sb',
        detail='Call BB'
    )
    
    log_result = action_logger.log(applied_action, log_context)
    print(f"  Logging result: {log_result}")
    
    # Verify the action was logged
    cursor.execute("SELECT action, amount, detail FROM actions WHERE player_id = 0")
    logged_action = cursor.fetchone()
    print(f"  Logged action: {logged_action}")
    print()
    
    # 7. Check if phase should advance
    print("Step 5: Check if phase should advance")
    should_advance = rules_engine.should_advance_phase(new_state)
    print(f"  Should advance phase: {should_advance}")
    
    if should_advance:
        next_phase = rules_engine.get_next_phase(new_state.phase)
        print(f"  Next phase: {next_phase.value}")
        
        # Log phase advance
        phase_context = LogContext(
            hand_id=1,
            game_session_id=1,
            step_number=2,
            phase=next_phase,
            detail='Advance to flop'
        )
        action_logger.log_phase_advance(new_state.phase.value, next_phase.value, phase_context)
        print("  Phase advance logged")
    
    print()
    print("=== Demo Complete ===")
    print("\nKey Benefits:")
    print("1. RulesEngine: Pure functions, easy to test, no side effects")
    print("2. ActionLogger: Simple database operations, easy to mock")
    print("3. Clean separation: Rules changes don't affect logging, logging changes don't affect rules")
    print("4. Fast unit tests: RulesEngine tests run without database")
    
    conn.close()


if __name__ == "__main__":
    demonstrate_clean_architecture()
