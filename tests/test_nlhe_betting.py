import pytest
from quads.engine.player import Player
from quads.engine.base_controller import GlobalScriptController
from quads.engine.hand import Hand
from quads.engine.extras import Action

def test_nlhe_minimum_raise_logic():
    # This script tests: min raise preflop, min raise after a raise, all-in for less, and postflop bet/raise
    script = [
        # Preflop: Alice raises to 2.0 (min raise, BB=1.0)
        ("alice", Action.RAISE, 2.0),
        # Bob raises to 4.0 (min raise is 2.0, since last raise was 1.0)
        ("bob", Action.RAISE, 4.0),
        # Alice calls
        ("alice", Action.CALL, 2.0),
        # Flop: Bob bets 3.0 (min bet is BB)
        ("bob", Action.BET, 3.0),
        # Alice raises to 6.0 (min raise is 3.0)
        ("alice", Action.RAISE, 6.0),
        # Bob goes all-in for 7.0 (less than a full raise)
        ("bob", Action.RAISE, 7.0),
        # Alice calls
        ("alice", Action.CALL, 1.0),
    ]

    def validate_min_raise(player, action, amount, game_state):
        if action in [Action.RAISE, Action.BET]:
            min_raise = game_state['valid_actions']['min_raise']
            max_raise = game_state['valid_actions']['max_raise']
            # Allow all-in for less
            if amount < min_raise:
                assert amount == player.stack + amount, "Only all-in for less can be below min raise"
            else:
                assert min_raise <= amount <= max_raise, f"Raise {amount} not in range {min_raise}-{max_raise}"

    controller = GlobalScriptController(script, test_hooks={'pre_action': validate_min_raise})
    players = [
        Player(name="alice", stack=10.0, controller=controller),
        Player(name="bob", stack=10.0, controller=controller),
    ]
    for i, p in enumerate(players):
        p.seat_index = i

    hand = Hand(
        players=players,
        small_blind=0.5,
        big_blind=1.0,
        dealer_index=0,
        hand_id="nlhe_betting_test"
    )
    hand.play()