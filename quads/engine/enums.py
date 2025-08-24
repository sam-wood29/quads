from enum import Enum


class Phase(str, Enum):
    DEAL = "deal"
    PREFLOP = "preflop"
    FLOP = "flop"
    TURN = "turn"
    RIVER = "river"
    SHOWDOWN = "showdown"


class ActionType(str, Enum):
    CALL = "call"
    RAISE = "raise"
    CHECK = "check"
    FOLD = "fold"
    BET = "bet"
    DEAL_HOLE = "deal_hole"
    DEAL_COMMUNITY = "deal_community"
    WIN_POT = "win_pot"
    POST_SMALL_BLIND = "post_small_blind"
    POST_BIG_BLIND = "post_big_blind"


class RaiseSetting(Enum):
    STANDARD = "standard"