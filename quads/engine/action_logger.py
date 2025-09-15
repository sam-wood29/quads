"""
Action Logger - Database operations for poker actions.

This module handles all database logging operations.
No game logic, just persistence of actions and state.
"""

import json
import sqlite3
from typing import Any

from .action_data import AppliedAction, LogContext
from .enums import ActionType
from .money import from_cents


class ActionLogger:
    """
    Handles database logging of poker actions.
    
    Pure side effects - no game logic, just persistence.
    """
    
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
    
    def log(self, applied_action: AppliedAction, context: LogContext) -> bool:
        """
        Log an applied action to the database.
        
        Args:
            applied_action: The action that was applied
            context: Context information for logging
            
        Returns:
            True if logging succeeded, False otherwise
        """
        try:
            cursor = self.conn.cursor()
            
            # Convert cents to dollars for database
            amount_dollars = from_cents(applied_action.amount) if applied_action.amount else None
            
            # Extract player information from state
            player_data = self._extract_player_data(applied_action.state_after, applied_action.player_id)
            
            # Prepare the database record
            db_record = (
                context.game_session_id,
                context.hand_id,
                context.step_number,
                applied_action.player_id,
                context.position,
                context.phase.value,
                applied_action.action_type.value,
                amount_dollars,
                context.hole_cards,
                player_data.get('hole_card1'),
                player_data.get('hole_card2'),
                context.community_cards,
                player_data.get('hand_rank_5'),
                player_data.get('hand_class'),
                player_data.get('pf_hand_class'),
                player_data.get('high_rank'),
                player_data.get('low_rank'),
                player_data.get('is_pair'),
                player_data.get('is_suited'),
                player_data.get('gap'),
                player_data.get('chen_score'),
                player_data.get('amount_to_call'),
                player_data.get('percent_stack_to_call'),
                player_data.get('highest_bet'),
                player_data.get('pot_odds'),
                context.detail
            )
            
            # Insert the record
            cursor.execute("""
                INSERT INTO actions (
                    game_session_id, hand_id, step_number, player_id, position, phase, action, amount,
                    hole_cards, hole_card1, hole_card2, community_cards,
                    hand_rank_5, hand_class, pf_hand_class, high_rank, low_rank, is_pair, is_suited, gap, chen_score,
                    amount_to_call, percent_stack_to_call, highest_bet, pot_odds, detail
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, db_record)
            
            self.conn.commit()
            return True
            
        except Exception as e:
            print(f"ERROR - Failed to log action: {e}")
            return False
    
    def log_phase_advance(self, from_phase: str, to_phase: str, context: LogContext) -> bool:
        """
        Log a phase advance action.
        
        Args:
            from_phase: Phase transitioning from
            to_phase: Phase transitioning to
            context: Context information for logging
            
        Returns:
            True if logging succeeded, False otherwise
        """
        try:
            cursor = self.conn.cursor()
            
            detail = json.dumps({
                "from": from_phase,
                "to": to_phase,
                "street_number": getattr(context, 'street_number', 0)
            })
            
            cursor.execute("""
                INSERT INTO actions (
                    game_session_id, hand_id, step_number, player_id, position, phase, action, amount,
                    community_cards, detail
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                context.game_session_id,
                context.hand_id,
                context.step_number,
                None,  # No player for phase advances
                None,  # No position for phase advances
                to_phase,
                ActionType.PHASE_ADVANCE.value,
                None,  # No amount for phase advances
                context.community_cards,
                detail
            ))
            
            self.conn.commit()
            return True
            
        except Exception as e:
            print(f"ERROR - Failed to log phase advance: {e}")
            return False
    
    def log_pot_award(self, winner_id: int, amount_cents: int, context: LogContext) -> bool:
        """
        Log a pot award action.
        
        Args:
            winner_id: ID of the player who won the pot
            amount_cents: Amount won in cents
            context: Context information for logging
            
        Returns:
            True if logging succeeded, False otherwise
        """
        try:
            cursor = self.conn.cursor()
            
            amount_dollars = from_cents(amount_cents)
            
            cursor.execute("""
                INSERT INTO actions (
                    game_session_id, hand_id, step_number, player_id, position, phase, action, amount,
                    detail
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                context.game_session_id,
                context.hand_id,
                context.step_number,
                winner_id,
                context.position,
                context.phase.value,
                ActionType.WIN_POT.value,
                amount_dollars,
                context.detail or "Pot award"
            ))
            
            self.conn.commit()
            return True
            
        except Exception as e:
            print(f"ERROR - Failed to log pot award: {e}")
            return False
    
    def _extract_player_data(self, state_after: dict[str, Any], player_id: int) -> dict[str, Any]:
        """Extract player-specific data from state for logging."""
        # Find the player in the state
        for player in state_after.get('players', []):
            if player.get('id') == player_id:
                return {
                    'hole_card1': player.get('hole_card1'),
                    'hole_card2': player.get('hole_card2'),
                    'hand_rank_5': player.get('hand_rank_5'),
                    'hand_class': player.get('hand_class'),
                    'pf_hand_class': player.get('pf_hand_class'),
                    'high_rank': player.get('high_rank'),
                    'low_rank': player.get('low_rank'),
                    'is_pair': player.get('is_pair'),
                    'is_suited': player.get('is_suited'),
                    'gap': player.get('gap'),
                    'chen_score': player.get('chen_score'),
                    'amount_to_call': player.get('amount_to_call'),
                    'percent_stack_to_call': player.get('percent_stack_to_call'),
                    'highest_bet': state_after.get('highest_bet'),
                    'pot_odds': player.get('pot_odds')
                }
        
        return {}
