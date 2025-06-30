from quads.engine.logging_utils import setup_logger
from quads.engine.core_game import Game, Player, Action, Phase, Position, ManualInputController
from quads.deuces import Deck, Card
from datetime import datetime
from pprint import pformat
import logging

log = setup_logger(name="quads",
             log_file='logs/smoke.log',
             mode='a',
             level=logging.INFO)

log.info(f'Logger Created at filename {log.name}, {datetime.now()}')

game = Game(players=[
    Player(stack=100, name='steve', controller=ManualInputController()),
    Player(stack=100, name='rodger', controller=ManualInputController()),
    Player(stack=100, name='mike', controller=ManualInputController()),
    Player(stack=100, name='allen', controller=ManualInputController()),
    Player(stack=100, name='paige', controller=ManualInputController())
])

game.assign_seat_seat_index_to_game_players()
# ---------WRAP IN LARGER METHOD ---------------#############
# reset players
[p.reset_for_new_hand() for p in game.players]
# a debug statement for the larger method.....
example_list = game.players[:2]
for p in example_list:
    log.debug(f'name: {p.name}, has_folded: {p.has_folded}, current_bet: {p.current_bet}, '
              f'cards: ({Card.int_to_str(p.hole_cards[0])}, {Card.int_to_str(p.hole_cards[1])})')
    
# reset the pot
game.pot = 0.0
# assign positions
ordered_ap_list = game.assign_player_positions()

log.info(f'Working from here...line 43 smoke_check.py')
log.info(f'debugging run betting round logic, trying to make it understandable')
log.info(f'current game state....')
log.info(str(game.__str__()))

game.post_blinds(ordered_ap_list=ordered_ap_list)

game.run_betting_round(phase=Phase.PREFLOP,
                       active_player_list=ordered_ap_list)











# --------------------------------------------------------------