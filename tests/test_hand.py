from quads.engine.logging_utils import setup_logger
from quads.engine.player import Player
from quads.engine.extras import Action, Phase
from quads.engine.hand import Hand
from quads.engine.base_controller import GlobalScriptController
from quads.deuces import Card, Deck
from pprint import pformat
import random
import logging
import pytest

log = setup_logger(name='hand_test',
                   log_file='logs/hand_test.log',
                   level=logging.DEBUG)

@pytest.fixture()
def scripted_players():
    """Create players with scripted controllers for testing."""
    # Define a script for a simple hand: everyone calls preflop, then folds
    script = [
        # Preflop actions (UTG, Button, SB, BB)
        ("dave", Action.CALL, None),    # UTG calls BB
        ("alice", Action.CALL, None),      # Button calls
        ("bob", Action.CALL, None),  # SB calls
        ("charlie", Action.CHECK, None),    # BB checks (no raise)
        
        # Flop actions (Button, SB, BB, UTG)
        ("bob", Action.BET, 1.0),     # SB Bets
        ("charlie", Action.FOLD, None),   # BB folds
        ("dave", Action.FOLD, None),     # UTG folds
        ("alice", Action.FOLD, None),    # Button Folds
    ]
    shared_controller = GlobalScriptController(script)
    players = [
        Player(name="alice", stack=100.0, controller=shared_controller),
        Player(name="bob", stack=100.0, controller=shared_controller),
        Player(name="charlie", stack=100.0, controller=shared_controller),
        Player(name="dave", stack=100.0, controller=shared_controller),
    ]
    
    # Assign seat indices
    for i, player in enumerate(players):
        player.seat_index = i
    
    return players

def test_complete_hand_with_script(scripted_players):
    """
    Test a complete hand using scripted actions.
    
    Expected flow:
    1. Preflop: Everyone calls/checks
    2. Flop: SB bets, everyone else folds
    3. Charlie wins the pot
    """
    # Create hand
    hand = Hand(
        players=scripted_players,
        small_blind=0.25,
        big_blind=0.50,
        dealer_index=0,  # Alice is dealer
        hand_id="test_hand_001"
    )
    
    # Play the hand
    result = hand.play()
    
    # Verify results
    assert len(result["winners"]) == 1
    assert result["winners"][0].name == "bob"
    
    # Verify pot distribution
    assert result["pot_distribution"][result["winners"][0]] == pytest.approx(2, abs=0.01)
    
    # Verify final stacks
    bob = next(p for p in scripted_players if p.name == "bob")
    assert bob.stack == pytest.approx(101.5, abs=0.01)  # 100 + 1.75 pot - 0.25 SB
    
    # Verify other players lost their blinds
    alice = next(p for p in scripted_players if p.name == "alice")
    charlie = next(p for p in scripted_players if p.name == "charlie")
    dave = next(p for p in scripted_players if p.name == "dave")
    
    assert alice.stack == pytest.approx(99.5, abs=0.01)   # 100 - 1.0 call
    assert charlie.stack == pytest.approx(99.5, abs=0.01)     # 100 - 1.0 call  
    assert dave.stack == pytest.approx(99.5, abs=0.01)    # 100 - 0.5 BB

def test_heads_up_hand():
    """Test a heads-up hand scenario."""
    # Simple heads-up script: both players check/call to showdown
    script = [
        # Preflop (Button, BB)
        ("alice", Action.CALL, None),    # Button calls BB
        ("bob", Action.CHECK, None),     # BB checks
        
        # Flop (Button, BB)
        ("bob", Action.CHECK, None),   # Button checks
        ("alice", Action.CHECK, None),     # BB checks
        
        # Turn (Button, BB)
        ("bob", Action.CHECK, None),   # Button checks
        ("alice", Action.CHECK, None),     # BB checks
        
        # River (Button, BB)
        ("bob", Action.CHECK, None),   # Button checks
        ("alice", Action.CHECK, None),     # BB checks
    ]
    script_controller = GlobalScriptController(script)
    players = [
        Player(name="alice", stack=100.0, controller=script_controller),
        Player(name="bob", stack=100.0, controller=script_controller),
    ]
    
    # Assign seat indices
    for i, player in enumerate(players):
        player.seat_index = i
    
    hand = Hand(
        players=players,
        small_blind=0.25,
        big_blind=0.50,
        dealer_index=0,
        hand_id="heads_up_test"
    )
    
    result = hand.play()
    
    # Should have a showdown with 2 players
    assert len(result["winners"]) >= 1
    assert len(result["hand_scores"]) >= 1
    
    # Total pot = Blinds + 0.25 cent call
    total_pot = sum(result["pot_distribution"].values())
    assert total_pot == pytest.approx(1, abs=0.01)

def test_all_fold_scenario():
    """Test scenario where everyone folds except one player."""
    script = [
        # Preflop: everyone folds except BB
        ("dave", Action.FOLD, None),    # UTG folds
        ("alice", Action.FOLD, None),      # Button folds
        ("bob", Action.FOLD, None),  # SB folds
        # BB doesn't need to act since everyone folded
    ]
    controller = GlobalScriptController(script=script)
    players = [
        Player(name="alice", stack=100.0, controller=controller),
        Player(name="bob", stack=100.0, controller=controller),
        Player(name="charlie", stack=100.0, controller=controller),
        Player(name="dave", stack=100.0, controller=controller),
    ]
    
    # Assign seat indices
    for i, player in enumerate(players):
        player.seat_index = i
    
    hand = Hand(
        players=players,
        small_blind=0.25,
        big_blind=0.50,
        dealer_index=0,
        hand_id="all_fold_test"
    )
    
    result = hand.play()
    
    assert len(result["winners"]) == 1
    assert result["winners"][0].name == "charlie"
    
    # charlie gets additional 0.25 from the SB
    charlie = next(p for p in players if p.name == "charlie")
    assert charlie.stack == pytest.approx(100.25, abs=0.01)  # 100 + 0.75 pot - 0.5 BB

def test_raise_and_reraise():
    """Test a hand with raises and reraises."""
    script = [
        # Preflop: UTG raises, Button reraises, others fold
        ("dave", Action.RAISE, 2.0),   # UTG raises to 2.0
        ("alice", Action.RAISE, 4.0),     # Button reraises to 4.0
        ("bob", Action.FOLD, None), # SB folds
        ("charlie", Action.CALL, 4),    # BB folds
        ("dave", Action.CALL, 2.0),
        
        # Postflop
        ("charlie", Action.RAISE, 2),
        ("dave", Action.FOLD, None),
        ("alice", Action.CALL, 2),
        
        # Turn - A silly fold haha.
        ("charlie", Action.FOLD, None)
    ]
    # pot pre = 4(dave) + 4(alice), 0.25(bob), 4(dave)
    # Flop =  +4
    # pot = 16.25
    
    controller = GlobalScriptController(script=script)
    players = [
        Player(name="alice", stack=100.0, controller=controller),
        Player(name="bob", stack=100.0, controller=controller),
        Player(name="charlie", stack=100.0, controller=controller),
        Player(name="dave", stack=100.0, controller=controller),
    ]
    
    # Assign seat indices
    for i, player in enumerate(players):
        player.seat_index = i
    
    hand = Hand(
        players=players,
        small_blind=0.25,
        big_blind=0.50,
        dealer_index=0,
        hand_id="raise_test"
    )
    
    result = hand.play()
    
    # Bob should win without showdown
    assert len(result["winners"]) == 1
    assert result["winners"][0].name == "alice"
    
    alice = next(p for p in players if p.name == "alice")
    assert alice.stack == pytest.approx(110.25, abs=0.01)
    
def test_more_complex_scenario():
    script = [
        # Preflop
        ("3", Action.CALL, 0.50),
        ("4", Action.RAISE, 1),
        ("5", Action.CALL, 1),
        ("6", Action.CALL, 1),
        ("0", Action.RAISE, 2),
        ("1", Action.CALL, 2),
        ("2", Action.CALL, 2),
        
        ("3", Action.FOLD, None),
        ("4", Action.FOLD, None),
        ("5", Action.CALL, 2),
        ("6", Action.RAISE, 3),
        ("0", Action.CALL, 3),
        ("1", Action.CALL, 3),
        ("2", Action.CALL, 3),
        
        ("5", Action.CALL, 3),
        # FLOP
        ("1", Action.CHECK, None),
        ("2", Action.RAISE, 1),
        ("5", Action.CALL, 1),
        ("6", Action.RAISE, 2),
        ("0", Action.CALL, 2),
        
        ("1", Action.CALL, 2),
        ("2", Action.CALL, 2),
        ("5", Action.FOLD, None),
        # TURN
        ("1", Action.CHECK, None),
        ("2", Action.CHECK, None),
        ("6", Action.RAISE, 1),
        ("0", Action.RAISE, 2),
        
        ("1", Action.RAISE, 3),
        ("2", Action.FOLD, None),
        ("6", Action.FOLD, None),
        ("0", Action.CALL, 3),
        # River
        ("1", Action.CHECK, None),
        ("0", Action.RAISE, 1),
        
        ("1", Action.FOLD, None),
    ]
    controller = GlobalScriptController(script=script)
    players = [
        Player(name='0', stack=10, controller=controller),
        Player(name='1', stack=10, controller=controller),
        Player(name='2', stack=10, controller=controller),
        Player(name='3', stack=10, controller=controller),
        Player(name='4', stack=10, controller=controller),
        Player(name='5', stack=10, controller=controller),
        Player(name='6', stack=10, controller=controller)
    ]
    for i, p in enumerate(players):
        p.seat_index = i
    
    hand = Hand(
        players=players,
        small_blind=0.25,
        big_blind=0.50,
        dealer_index=0,
        hand_id='more_complex_test'
    )
    result = hand.play()
    log.info('Pot Distribution...')
    log.info(pformat(result['pot_distribution']))
    player0 = next(p for p in players if p.name == '0')
    assert player0.stack == 34.5
    assert 1 == 2 # Keep this here to see output