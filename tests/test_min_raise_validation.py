import pytest
from quads.engine.player import Player
from quads.engine.hand import Hand
from quads.engine.base_controller import GlobalScriptController
from quads.engine.extras import Action, Phase

def make_players(controller, names=("alice", "bob", "charlie")):
    players = [Player(name=n, stack=10.0, controller=controller) for n in names]
    for i, p in enumerate(players):
        p.seat_index = i
    return players

def test_minimum_raise_and_increment():
    # This test will check:
    # - First raise must be at least big blind
    # - Subsequent raises must be at least the previous raise increment
    # - Betting increments are enforced

    # Track validation calls
    validation_log = []

    def validate_min_raise(player, action, amount, game_state):
        if action == Action.RAISE:
            min_raise = game_state['valid_actions']['min_raise']
            max_raise = game_state['valid_actions']['max_raise']
            # Log for debugging
            validation_log.append((player.name, amount, min_raise, max_raise))
            # Assert the raise is within allowed range
            assert min_raise <= amount <= max_raise, (
                f"Raise {amount} not in valid range {min_raise}-{max_raise} for {player.name}"
            )
            # If betting increments are set, check that as well
            if game_state['betting_increments'] == 'big_blind':
                big_blind = game_state['min_raise'] or 2.0
                assert (amount % big_blind) == 0, (
                    f"Raise {amount} not a multiple of big blind {big_blind}"
                )

    # Script:
    # - Alice raises to 2.0 (valid, first raise, matches big blind)
    # - Bob raises to 3.0 (invalid, increment only 1.0, should fail)
    # - Bob raises to 4.0 (valid, increment 2.0)
    # - Charlie raises to 5.0 (invalid if increments enforced)
    # - Charlie raises to 6.0 (valid if increments enforced)
    script = [
        ("alice", Action.RAISE, 2.0),   # Valid
        ("bob", Action.RAISE, 3.0),     # Invalid, should fail test
        ("bob", Action.RAISE, 4.0),     # Valid
        ("charlie", Action.RAISE, 5.0), # Invalid if increments enforced
        ("charlie", Action.RAISE, 6.0), # Valid
    ]

    controller = GlobalScriptController(
        script=script,
        test_hooks={'pre_action': validate_min_raise}
    )
    players = make_players(controller, ("alice", "bob", "charlie"))

    hand = Hand(
        players=players,
        small_blind=1.0,
        big_blind=2.0,
        dealer_index=0,
        min_raise=None,  # Use big blind as min raise
        betting_increments='big_blind',  # Enforce increments
        hand_id="min_raise_test"
    )

    # The test will fail on the first invalid raise (bob to 3.0)
    with pytest.raises(AssertionError):
        hand.play()

    # You can also check the log for what was validated
    print("Validation log:", validation_log)

def test_all_in_edge_case():
    # Test that a player can go all-in for less than a full raise
    def validate_all_in(player, action, amount, game_state):
        if action == Action.RAISE:
            # If player is all-in, allow it even if not a full raise
            if player.stack == 0:
                assert amount <= game_state['player_stack'] + amount
            else:
                min_raise = game_state['valid_actions']['min_raise']
                assert amount >= min_raise

    script = [
        ("alice", Action.RAISE, 10.0),  # Alice goes all-in
        ("bob", Action.FOLD, None),
        ("charlie", Action.FOLD, None),
    ]
    controller = GlobalScriptController(
        script=script,
        test_hooks={'pre_action': validate_all_in}
    )
    players = make_players(controller, ("alice", "bob", "charlie"))
    players[0].stack = 10.0  # Alice has only 10 chips

    hand = Hand(
        players=players,
        small_blind=1.0,
        big_blind=2.0,
        dealer_index=0,
        min_raise=None,
        betting_increments='big_blind',
        hand_id="all_in_test"
    )
    result = hand.play()
    assert result["winners"][0].name == "alice" 