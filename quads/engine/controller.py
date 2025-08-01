from enum import Enum

class ControllerType(Enum):
    SCRIPT = "script"
    MANUAL = "manual"


class Controller:
    def __init__(self, controller_type: ControllerType):
        self.controller_type = controller_type
    
def _script_decide(hand):
    print("hello_world")