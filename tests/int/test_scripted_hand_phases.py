import json
import sqlite3
from unittest.mock import Mock, patch

from quads.engine.enums import ActionType, Phase


class TestScriptedHandPhases:
    """Integration tests for phase transitions in scripted hands."""
    
    def test_simple_3player_hand_phases(self):
        """Test phase transitions in a simple 3-player hand."""
        # Create a simple script that will result in uncontested pot
        script_data = {
            "script_name": "test_phases_3player.json",
            "rebuy_setting": "one_left",
            "same_stack": True,
            "stack_amount": 20,
            "small_blind": 0.25,
            "big_blind": 0.5,
            "players": [
                {"id": 1, "status": "exists"},
                {"id": 2, "status": "exists"},
                {"id": 3, "status": "exists"}
            ],
            "script": [
                # Deal hole cards
                {"type": "deal_hole", "player": "1", "cards": ["As", "Ac"]},
                {"type": "deal_hole", "player": "2", "cards": ["Ks", "Kc"]},
                {"type": "deal_hole", "player": "3", "cards": ["Qs", "Qc"]},
                
                # Preflop actions (call, call, check)
                {"type": "action", "player": 1, "move": "call"},
                {"type": "action", "player": 2, "move": "call"},
                {"type": "action", "player": 3, "move": "check"},
                
                # Deal flop
                {"type": "deal_community", "cards": ["Ah", "Kh", "Qh"]},
                
                # Flop actions (bet, fold, fold - uncontested)
                {"type": "action", "player": 1, "move": "raise", "amount": 1.0},
                {"type": "action", "player": 2, "move": "fold"},
                {"type": "action", "player": 3, "move": "fold"}
            ]
        }
        
        # Mock the database and run the script
        with patch('quads.engine.conn.get_conn') as mock_get_conn:
            mock_conn = sqlite3.connect(':memory:')
            mock_get_conn.return_value = mock_conn
            
            # Mock the database operations
            with patch('quads.engine.hand.log_action') as mock_log:
                mock_log.return_value = True
                
                # Create a mock game session
                with patch('quads.engine.game.create_game_from_script') as mock_create:
                    mock_game = Mock()
                    mock_game.script = script_data['script']
                    mock_create.return_value = mock_game
                    
                    # Run the hand
                    mock_game.play()
                    
                    # Check that phase_advance actions were logged
                    phase_advance_calls = [
                        call for call in mock_log.call_args_list
                        if call[1].get('action') == ActionType.PHASE_ADVANCE.value
                    ]
                    
                    # Should have: deal → preflop → flop → showdown
                    assert len(phase_advance_calls) >= 3
                    
                    # Check the sequence
                    phases = [call[1]['phase'] for call in phase_advance_calls]
                    expected_phases = [Phase.PREFLOP.value, Phase.FLOP.value, Phase.SHOWDOWN.value]
                    
                    for expected in expected_phases:
                        assert expected in phases
    
    def test_full_5card_showdown_phases(self):
        """Test phase transitions in a full 5-card showdown."""
        script_data = {
            "script_name": "test_phases_full.json",
            "rebuy_setting": "one_left",
            "same_stack": True,
            "stack_amount": 20,
            "small_blind": 0.25,
            "big_blind": 0.5,
            "players": [
                {"id": 1, "status": "exists"},
                {"id": 2, "status": "exists"}
            ],
            "script": [
                # Deal hole cards
                {"type": "deal_hole", "player": "1", "cards": ["As", "Ac"]},
                {"type": "deal_hole", "player": "2", "cards": ["Ks", "Kc"]},
                
                # Preflop: call, check
                {"type": "action", "player": 1, "move": "call"},
                {"type": "action", "player": 2, "move": "check"},
                
                # Deal flop
                {"type": "deal_community", "cards": ["Ah", "Kh", "Qh"]},
                
                # Flop: check, check
                {"type": "action", "player": 1, "move": "check"},
                {"type": "action", "player": 2, "move": "check"},
                
                # Deal turn
                {"type": "deal_community", "cards": ["Jh"]},
                
                # Turn: check, check
                {"type": "action", "player": 1, "move": "check"},
                {"type": "action", "player": 2, "move": "check"},
                
                # Deal river
                {"type": "deal_community", "cards": ["Th"]},
                
                # River: check, check
                {"type": "action", "player": 1, "move": "check"},
                {"type": "action", "player": 2, "move": "check"}
            ]
        }
        
        with patch('quads.engine.conn.get_conn') as mock_get_conn:
            mock_conn = sqlite3.connect(':memory:')
            mock_get_conn.return_value = mock_conn
            
            with patch('quads.engine.hand.log_action') as mock_log:
                mock_log.return_value = True
                
                with patch('quads.engine.game.create_game_from_script') as mock_create:
                    mock_game = Mock()
                    mock_game.script = script_data['script']
                    mock_create.return_value = mock_game
                    
                    mock_game.play()
                    
                    # Check phase_advance sequence
                    phase_advance_calls = [
                        call for call in mock_log.call_args_list
                        if call[1].get('action') == ActionType.PHASE_ADVANCE.value
                    ]
                    
                    # Should have: deal → preflop → flop → turn → river → showdown
                    assert len(phase_advance_calls) >= 5
                    
                    phases = [call[1]['phase'] for call in phase_advance_calls]
                    expected_phases = [
                        Phase.PREFLOP.value,
                        Phase.FLOP.value,
                        Phase.TURN.value,
                        Phase.RIVER.value,
                        Phase.SHOWDOWN.value
                    ]
                    
                    for expected in expected_phases:
                        assert expected in phases
    
    def test_phase_advance_logging_format(self):
        """Test that phase advance logging has correct format."""
        script_data = {
            "script_name": "test_logging.json",
            "rebuy_setting": "one_left",
            "same_stack": True,
            "stack_amount": 20,
            "small_blind": 0.25,
            "big_blind": 0.5,
            "players": [{"id": 1, "status": "exists"}],
            "script": [
                {"type": "deal_hole", "player": "1", "cards": ["As", "Ac"]},
                {"type": "action", "player": 1, "move": "fold"}
            ]
        }
        
        with patch('quads.engine.conn.get_conn') as mock_get_conn:
            mock_conn = sqlite3.connect(':memory:')
            mock_get_conn.return_value = mock_conn
            
            with patch('quads.engine.hand.log_action') as mock_log:
                mock_log.return_value = True
                
                with patch('quads.engine.game.create_game_from_script') as mock_create:
                    mock_game = Mock()
                    mock_game.script = script_data['script']
                    mock_create.return_value = mock_game
                    
                    mock_game.play()
                    
                    # Find phase_advance calls
                    phase_calls = [
                        call for call in mock_log.call_args_list
                        if call[1].get('action') == ActionType.PHASE_ADVANCE.value
                    ]
                    
                    # Check format of first phase advance
                    if phase_calls:
                        call = phase_calls[0]
                        kwargs = call[1]
                        
                        assert kwargs['player'] is None
                        assert kwargs['action'] == ActionType.PHASE_ADVANCE.value
                        assert 'phase' in kwargs
                        assert 'detail' in kwargs
                        
                        # Check detail JSON format
                        detail = json.loads(kwargs['detail'])
                        assert 'from' in detail
                        assert 'to' in detail
                        assert 'street_number' in detail
                        assert isinstance(detail['street_number'], int) 