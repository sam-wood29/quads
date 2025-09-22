"""
Smoke test for ActionLogger - Database logging operations.

This test demonstrates that the ActionLogger can log actions to the database.
"""

import os
import sqlite3
import tempfile

from quads.engine.action_data import AppliedAction, LogContext
from quads.engine.action_logger import ActionLogger
from quads.engine.enums import ActionType, Phase
from quads.engine.money import to_cents


class TestActionLogger:
    """Test the ActionLogger database operations."""
    
    def setup_method(self):
        """Set up test database."""
        # Create a temporary database file
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        
        # Create connection and schema
        self.conn = sqlite3.connect(self.temp_db.name)
        self._create_test_schema()
        
        # Create ActionLogger
        self.logger = ActionLogger(self.conn)
    
    def teardown_method(self):
        """Clean up test database."""
        self.conn.close()
        os.unlink(self.temp_db.name)
    
    def _create_test_schema(self):
        """Create minimal test schema."""
        cursor = self.conn.cursor()
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
        self.conn.commit()
    
    def test_log_call_action(self):
        """Test logging a call action."""
        # Create test data
        applied_action = AppliedAction(
            player_id=0,
            action_type=ActionType.CALL,
            amount=to_cents(0.25),
            state_before={
                'hand_id': 1,
                'phase': 'preflop',
                'pot_cents': to_cents(0.75),
                'highest_bet': to_cents(0.50),
                'players': [
                    {
                        'id': 0,
                        'stack': to_cents(100.0),
                        'current_bet': to_cents(0.25),
                        'hand_contrib': to_cents(0.25)
                    }
                ]
            },
            state_after={
                'hand_id': 1,
                'phase': 'preflop',
                'pot_cents': to_cents(1.00),
                'highest_bet': to_cents(0.50),
                'players': [
                    {
                        'id': 0,
                        'stack': to_cents(99.75),
                        'current_bet': to_cents(0.50),
                        'hand_contrib': to_cents(0.50)
                    }
                ]
            },
            metadata={'phase': 'preflop', 'hand_id': 1}
        )
        
        context = LogContext(
            hand_id=1,
            game_session_id=1,
            step_number=3,
            phase=Phase.PREFLOP,
            position='sb',
            hole_cards='Ah,Kh',
            community_cards='',
            pot_amount=to_cents(1.00),
            detail='Call BB'
        )
        
        # Log the action
        result = self.logger.log(applied_action, context)
        
        # Verify logging succeeded
        assert result is True
        
        # Verify data was written to database
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM actions WHERE player_id = 0 AND action = 'call'")
        row = cursor.fetchone()
        
        assert row is not None
        # Column indices: 0=id, 1=game_session_id, 2=hand_id, 3=step_number, 4=player_id, 5=position, 6=phase, 7=action, 8=amount
        assert row[4] == 0  # player_id
        assert row[6] == 'preflop'  # phase
        assert row[7] == 'call'  # action
        assert row[8] == 0.25  # amount (converted to dollars)
        assert row[9] == 'Ah,Kh'  # hole_cards
        assert row[26] == 'Call BB'  # detail (last column)
    
    def test_log_raise_action(self):
        """Test logging a raise action."""
        applied_action = AppliedAction(
            player_id=0,
            action_type=ActionType.RAISE,
            amount=to_cents(2.00),
            state_before={
                'hand_id': 1,
                'phase': 'preflop',
                'pot_cents': to_cents(0.75),
                'highest_bet': to_cents(0.50),
                'players': [
                    {
                        'id': 0,
                        'stack': to_cents(100.0),
                        'current_bet': to_cents(0.25),
                        'hand_contrib': to_cents(0.25)
                    }
                ]
            },
            state_after={
                'hand_id': 1,
                'phase': 'preflop',
                'pot_cents': to_cents(2.25),
                'highest_bet': to_cents(2.00),
                'players': [
                    {
                        'id': 0,
                        'stack': to_cents(98.25),
                        'current_bet': to_cents(2.00),
                        'hand_contrib': to_cents(2.00)
                    }
                ]
            },
            metadata={'phase': 'preflop', 'hand_id': 1}
        )
        
        context = LogContext(
            hand_id=1,
            game_session_id=1,
            step_number=4,
            phase=Phase.PREFLOP,
            position='sb',
            hole_cards='Ah,Kh',
            community_cards='',
            pot_amount=to_cents(2.25),
            detail='Raise to $2.00'
        )
        
        # Log the action
        result = self.logger.log(applied_action, context)
        
        # Verify logging succeeded
        assert result is True
        
        # Verify data was written to database
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM actions WHERE player_id = 0 AND action = 'raise'")
        row = cursor.fetchone()
        
        assert row is not None
        assert row[7] == 'raise'  # action
        assert row[8] == 2.00  # amount (converted to dollars)
        assert row[26] == 'Raise to $2.00'  # detail (last column)
    
    def test_log_phase_advance(self):
        """Test logging a phase advance."""
        context = LogContext(
            hand_id=1,
            game_session_id=1,
            step_number=5,
            phase=Phase.FLOP,
            position=None,
            community_cards='7s,2c,9h',
            pot_amount=to_cents(1.00),
            detail='Advance to flop'
        )
        
        # Log the phase advance
        result = self.logger.log_phase_advance('preflop', 'flop', context)
        
        # Verify logging succeeded
        assert result is True
        
        # Verify data was written to database
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM actions WHERE action = 'phase_advance'")
        row = cursor.fetchone()
        
        assert row is not None
        assert row[4] is None  # player_id (no player for phase advances)
        assert row[6] == 'flop'  # phase
        assert row[7] == 'phase_advance'  # action
        assert row[8] is None  # amount (no amount for phase advances)
        assert row[12] == '7s,2c,9h'  # community_cards
    
    def test_log_pot_award(self):
        """Test logging a pot award."""
        context = LogContext(
            hand_id=1,
            game_session_id=1,
            step_number=10,
            phase=Phase.SHOWDOWN,
            position='bb',
            community_cards='7s,2c,9h,5d,3d',
            pot_amount=to_cents(2.00),
            detail='Won pot with Pair'
        )
        
        # Log the pot award
        result = self.logger.log_pot_award(1, to_cents(2.00), context)
        
        # Verify logging succeeded
        assert result is True
        
        # Verify data was written to database
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM actions WHERE action = 'win_pot'")
        row = cursor.fetchone()
        
        assert row is not None
        assert row[4] == 1  # player_id
        assert row[6] == 'showdown'  # phase
        assert row[7] == 'win_pot'  # action
        assert row[8] == 2.00  # amount (converted to dollars)
        assert row[26] == 'Won pot with Pair'  # detail (last column)
    
    def test_log_multiple_actions(self):
        """Test logging multiple actions in sequence."""
        actions = [
            (ActionType.CALL, to_cents(0.25), 'Call BB'),
            (ActionType.RAISE, to_cents(2.00), 'Raise to $2.00'),
            (ActionType.FOLD, 0, 'Fold to raise')
        ]
        
        for i, (action_type, amount, detail) in enumerate(actions):
            applied_action = AppliedAction(
                player_id=i % 2,  # Alternate between players
                action_type=action_type,
                amount=amount,
                state_before={'hand_id': 1, 'phase': 'preflop'},
                state_after={'hand_id': 1, 'phase': 'preflop'},
                metadata={'phase': 'preflop', 'hand_id': 1}
            )
            
            context = LogContext(
                hand_id=1,
                game_session_id=1,
                step_number=i + 1,
                phase=Phase.PREFLOP,
                position='sb' if i % 2 == 0 else 'bb',
                detail=detail
            )
            
            result = self.logger.log(applied_action, context)
            assert result is True
        
        # Verify all actions were logged
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM actions")
        count = cursor.fetchone()[0]
        assert count == 3
        
        # Verify specific actions
        cursor.execute("SELECT action FROM actions ORDER BY step_number")
        actions_logged = [row[0] for row in cursor.fetchall()]
        assert actions_logged == ['call', 'raise', 'fold']
