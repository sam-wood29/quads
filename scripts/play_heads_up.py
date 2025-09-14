from quads.engine.base_controller import ManualInputController

from quads.engine.game import Game
from quads.engine.player import Player


def main():
    # Fixed player order: Alice (Button), Bob (BB)
    alice = Player(name="Alice", stack=50.0, controller=ManualInputController())
    bob = Player(name="Bob", stack=50.0, controller=ManualInputController())
    players = [alice, bob]
    for i, p in enumerate(players):
        p.seat_index = i

    game = Game(
        small_blind=0.25,
        big_blind=0.50,
        players=players
    )
    # Assign seats in order (no shuffle)
    game.assign_seats(rng=None)
    game.play_hand("manual_heads_up")

if __name__ == "__main__":
    main()