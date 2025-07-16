from quads.engine.player import Player
from quads.engine.base_controller import ManualInputController
from quads.engine.game import Game

def main():
    # Fixed player order: Alice (Button), Bob (SB), Charlie (BB)
    alice = Player(name="Alice", stack=50.0, controller=ManualInputController())
    bob = Player(name="Bob", stack=50.0, controller=ManualInputController())
    charlie = Player(name="Charlie", stack=50.0, controller=ManualInputController())
    players = [alice, bob, charlie]
    for i, p in enumerate(players):
        p.seat_index = i

    game = Game(
        small_blind=0.25,
        big_blind=0.50,
        players=players
    )
    # Assign seats in order (no shuffle)
    game.assign_seats(rng=None)
    print("Starting 3-player game (Alice = Button, Bob = SB, Charlie = BB)")
    game.play_hand("manual_three_player")

if __name__ == "__main__":
    main() 