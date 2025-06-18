from quads.engine.logging_utils import setup_logger
from quads.engine.core_game import Game, Player, Hand
from datetime import datetime
from pprint import pformat

smoke = setup_logger(name=__name__,
             log_file='logs/smoke.log',
             mode='a')

smoke.info(f'Logger Created at filename {smoke.name}, {datetime.now()}')
smoke.info('executing scripts/smoke_check.py')

game = Game(players=[
    Player(stack=100, name='steve'),
    Player(stack=100, name='rodger'),
    Player(stack=100, name='mike'),
    Player(stack=100, name='allen'),
])

# Assign players seats within the game
smoke.info('game.assign_players_ingame_new_seats()')
game.assign_players_ingame_new_seats()
player_seat_data = {player.name: player.seat_index for player in game.players}
smoke.info(pformat(player_seat_data, sort_dicts=False))

# Assign positions to players based on their seats
smoke.info('game.assign_player_positions_for_hand()')
game.assign_player_positions_for_hand()
game.players.sort(key=lambda player: player.seat_index)
player_pos_data = {
    player.name: (player.seat_index, player.position)
    for player in game.players
}
smoke.info(pformat(player_pos_data, sort_dicts=False))

# playing a hand
# build this out and verify as we go.
game.play_hand()
smoke.info("game.play_hand")
