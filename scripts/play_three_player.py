from quads.engine.base_controller import ManualInputController

from quads.engine.game import Game
from quads.engine.player import Player


def main():
    # Fixed player order: Alice (Button), Bob (SB), Charlie (BB)
    button = Player(name="button", stack=50.0, controller=ManualInputController())
    sb = Player(name="sb", stack=50.0, controller=ManualInputController())
    bb = Player(name="bb", stack=50.0, controller=ManualInputController())
    utg = Player(name="utg", stack=50.0, controller=ManualInputController())
    mp = Player(name="mp", stack=50.0, controller=ManualInputController())
    co = Player(name="co", stack=50.0, controller=ManualInputController())
    
    players = [button, sb, bb, utg, mp, co]
    for i, p in enumerate(players):
        p.seat_index = i

    game = Game(
        small_blind=0.25,
        big_blind=0.50,
        players=players
    )
    # Assign seats in order (no shuffle)
    game.assign_seats(rng=None)
    game.play_hand(hand_id='hand_0001')

if __name__ == "__main__":
    main() 