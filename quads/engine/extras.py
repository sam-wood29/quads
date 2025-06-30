from enum import Enum, auto


class Action(Enum):
    """
    Enum representing possible player actions.
    """
    FOLD = auto()
    CALL = auto()
    CHECK = auto()
    RAISE = auto()
    BET = auto()
    ALL_IN = auto()                  
    

class Phase(Enum):
    """
    Enum representing the current phase of the hand.
    """
    WAITING = "waiting"
    PREDEAL = "predeal"
    PREFLOP = "preflop"
    FLOP = "flop"
    TURN = "turn"
    RIVER = "river"
    SHOWDOWN = "showdown"


POSITIONS_BY_PLAYER_COUNT = {
    2: ["Button", "BB"],
    3: ["Button", "SB", "BB"],
    4: ["Button", "SB", "BB", "UTG"],
    5: ["Button", "SB", "BB", "UTG", "CO"],
    6: ["Button", "SB", "BB", "UTG", "HJ", "CO"],
    7: ["Button", "SB", "BB", "UTG", "MP", "HJ", "CO"],
    8: ["Button", "SB", "BB", "UTG", "UTG+1", "MP", "HJ", "CO"],
    9: ["Button", "SB", "BB", "UTG", "UTG+1", "UTG+2", "MP", "HJ", "CO"],
    10: ["Button", "SB", "BB", "UTG", "UTG+1", "UTG+2", "MP", "LJ", "HJ", "CO"]
}
