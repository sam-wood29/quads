from quads.engine.logging_utils import setup_logger
from quads.engine.player import Player
from quads.engine.extras import Action, Phase
from quads.engine.game import Game
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
    game=Game(
        small_blind=0.25,
        big_blind=0.5,
        players=[
            Player(name='paul',stack=100),
            Player(name='kim',stack=100),
            Player(name='nancy',stack=100),
            Player(name='linda',stack=100),
        ]
    )
    game.assign_seat_index_to_game_players(rng=random.Random(1))
    log.debug(f'players: {[(p.name, p.seat_index) for p in game.players]}')
    return game

def test_early_game(early_game):
    """
    Some Explanation of what I am testing here...

    Starting player position: linda (Button), paul (SB), nancy (BB), kim (UTG)

    """
    # 0. Create Game
    game = early_game
    # 1. Reset for new hand
    [p.reset_for_new_hand() for p in game.players]
    for p in game.players:
        assert not p.has_folded, f"{p.name} folded unexpectedly"
        assert p.current_bet == 0.0, f"{p.name} current_bet = {p.current_bet}"
        assert p.pot_contrib == 0.0, f"{p.name} pot_contrib = {p.pot_contrib}"
        assert len(p.hole_cards) == 2, f"{p.name} has {len(p.hole_cards)} hole cards"
        assert isinstance(p.hole_cards, list), f"{p.name}'s hole_cards not a list"
        # DEBUG
        # for c in p.hole_cards:
        #     log.debug(f'{p.name} card type: {type(c)}, value: {c}')
        assert all(isinstance(c, int) for c in p.hole_cards), f"{p.name} has non-Card hole cards"

    # 2. Reset Game 
    game.pot = 0.0

    # 3. Assign player positions
    dealer_ordered_players = game.assign_player_positions()
    linda = game.players[0]
    kim = game.players[3]
    assert linda.name == 'linda' and linda.position == 'Button', f'({linda.name}, {linda.position})'
    assert kim.name == 'kim' and kim.position == 'UTG', f'({kim.name}, {kim.position})'

    # 4. Post Blinds
    game.post_blinds(dealer_ordered_players)
    assert game.pot == 0.75
    paul = next(p for p in game.players if p.position == 'SB')
    assert paul.pot_contrib == 0.25, f'{paul.__str__()}'
    nancy = next(p for p in game.players if p.position == 'BB')
    assert nancy.pot_contrib == 0.50, f'{nancy.__str__()}'

    game.phase = Phase.PREFLOP
    # 5. Get action order of active players
    action_order = game.get_action_order()
    assert action_order[0].position == 'UTG' and action_order[0].name == 'kim', f'action_order: {[(p.position, p.name) for p in action_order]}'

    # 6. Verify FLOP/TURN?RIVER order works
    game.phase == Phase.FLOP
    action_order = game.get_action_order()
    assert action_order[0].name == 'kim'

    # 7. Run Preflop
    game.run_betting_round(phase=Phase.PREFLOP, active_player_list=action_order)
    

@pytest.fixture()
def heads_up_game():
    game=Game(
        small_blind=0.25,
        big_blind=0.5,
        players=[
            Player(name='mandy',stack=100),
            Player(name='joy',stack=100),
        ]
    )
    game.assign_seat_index_to_game_players(rng=random.Random(1))
    [p.reset_for_new_hand() for p in game.players]
    game.pot = 0.0
    dealer_ordered_players = game.assign_player_positions()
    game.post_blinds(dealer_ordered_players)
    return game
    
def test_heads_up(heads_up_game):
    '''
    
    starting position order: [('Button', 0, 'joy'), ('BB', 1, 'mandy')]
    '''
    # 1. Initalize game
    game = heads_up_game
    log.debug(f'DEBUG - {[(p.position, p.seat_index, p.name) for p in game.players]}')
    # 2. Blinds should be Good
    joy = next(p for p in game.players if p.position == 'Button')
    mandy = next(p for p in game.players if p.position == 'BB')
    assert joy.stack == 99.75

    # 2. Verify PREFLOP Action order
    game.phase = Phase.PREFLOP
    action_order = game.get_action_order()
    assert action_order[0].name == 'joy', f'action order 0: {action_order[0].name}'
    assert action_order[1].position == 'BB', f'{action_order[1].position}'

    