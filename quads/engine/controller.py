from enum import Enum

class ControllerType(Enum):
    GLOBAL_SCRIPT = "global_script"
    MANUAL = "manual"


class Controller:
    def __init__(self, controller_type: ControllerType):
        self.controller_type = controller_type