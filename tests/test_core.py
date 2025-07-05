from quads.engine.logging_utils import setup_logger
from quads.engine.player import Player
from quads.engine.base_controller import GlobalScriptController
from quads.engine.game import Game
from quads.engine.hand import Hand
from quads.engine.extras import Action
from quads.deuces import Deck, Card
from datetime import datetime
import random
import logging
import pytest

log = setup_logger(name='core',
                   log_file='logs/core_test.log',
                   level=logging.DEBUG)

@pytest.fixture()
def early_game():
    # Create a simple script for a 4-player hand
    script = [
        # Preflop actions (UTG, Button, SB, BB)
        ("kim", Action.CALL, None),     # UTG calls BB
        ("linda", Action.CALL, None),      # Button calls
        ("paul", Action.CALL, None),    # SB calls
        ("nancy", Action.CHECK, None),   # BB checks (no raise)
        
        # Flop actions (Button, SB, BB, UTG)
        ("paul", Action.CHECK, None),     # SB checks
        ("nancy", Action.BET, 1.0),      # BB bets 1.0
        ("kim", Action.FOLD, None),    # UTG folds
        ("linda", Action.FOLD, None),     # Button folds
        ("paul", Action.FOLD, None),      # SB folds (paul)
    ]
    
    shared_controller = GlobalScriptController(script)
    game = Game(
        small_blind=0.25,
        big_blind=0.5,
        players=[
            Player(name='paul', stack=100, controller=shared_controller),
            Player(name='kim', stack=100, controller=shared_controller),
            Player(name='nancy', stack=100, controller=shared_controller),
            Player(name='linda', stack=100, controller=shared_controller),
        ]
    )
    game.assign_seats(rng=random.Random(1))
    log.debug(f'players: {[(p.name, p.seat_index) for p in game.players]}')
    return game

def test_early_game(early_game):
    """
    Test basic game functionality.
    """
    # Create Game
    game = early_game
    
    # Test that we can play a hand
    result = game.play_hand("test_hand_001")
    
    # Verify we got a result
    assert "winners" in result
    assert "pot_distribution" in result
    
    # Verify session tracking
    summary = game.get_session_summary()
    assert summary["total_hands"] == 1

def test_heads_up_game():
    """Test heads-up game scenario."""
    # Create a simple script for heads-up
    script = [
        # Preflop (Button, BB)
        ("joy", Action.CALL, None),    # Button calls
        ("mandy", Action.CHECK, None),     # BB checks
        
        # Flop (Button, BB)
        ("mandy", Action.CHECK, None),   
        ("joy", Action.CHECK, None),     
        
        # Turn (Button, BB)
        ("mandy", Action.CHECK, None),   
        ("joy", Action.CHECK, None),     
        
        # River (Button, BB)
        ("mandy", Action.CHECK, None),   
        ("joy", Action.CHECK, None),     
    ]
    shared_controller = GlobalScriptController(script)
    game = Game(
        small_blind=0.25,
        big_blind=0.5,
        players=[
            Player(name='mandy', stack=100, controller=shared_controller),
            Player(name='joy', stack=100, controller=shared_controller),
        ]
    )
    game.assign_seats(rng=random.Random(1))
    
    # Play a hand
    result = game.play_hand("heads_up_test")
    
    # Should have a winner
    assert len(result["winners"]) >= 1
    
    log.info('player stacks...')
    for p in game.players:
        log.info(f'player {p.name}, stack {p.stack}')
    
    # Total pot should be 0.75 (blinds)
    total_pot = sum(result["pot_distribution"].values())
    assert total_pot == pytest.approx(1, abs=0.01)
    