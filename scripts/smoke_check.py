from quads.engine.logging_utils import setup_logger
from quads.engine.core_game import Game, Player, Action, Phase, Position, ManualInputController
from quads.deuces import Deck, Card
from datetime import datetime
from pprint import pformat
import logging

log = setup_logger(name="quads",
             log_file='logs/smoke.log',
             mode='a',
             level=logging.DEBUG)

log.info(f'Logger Created at filename {log.name}, {datetime.now()}')
log.info('executing scripts/smoke_check.py\n')

game = Game(players=[
    Player(stack=100, name='steve', controller=ManualInputController()),
    Player(stack=100, name='rodger', controller=ManualInputController()),
    Player(stack=100, name='mike', controller=ManualInputController()),
    Player(stack=100, name='allen', controller=ManualInputController()),
    Player(stack=100, name='paige', controller=ManualInputController())
])

game.assign_seat_seat_index_to_game_players()


# ---------WRAP IN LARGER METHOD ---------------

# reset players
[p.reset_for_new_hand() for p in game.players]
# a debug statement for the larger method.....
example_list = game.players[:2]
for p in example_list:
    log.debug(f'name: {p.name}, has_folded: {p.has_folded}, current_bet: {p.current_bet}, '
              f'cards: ({Card.int_to_str(p.hole_cards[0])}, {Card.int_to_str(p.hole_cards[1])})')
log.info('INFO ------------ Game Initalized ------------')

# assign positions
ordered_ap_list = game.assign_player_positions()

# post blinds
game.post_blinds(ordered_ap_list=ordered_ap_list)

# reset the pot
log.info('INFO - will need to reset action log/history hear')
game.pot = 0.0

# Run the betting logic
game.run_betting_round(phase=Phase.PREFLOP,
                       ordered_ap_list=ordered_ap_list)











# --------------------------------------------------------------