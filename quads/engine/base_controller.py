from typing import Tuple, Optional
from quads.engine.extras import Action
import logging


class BaseController:
    def decide(self, player, game_state, **kwargs) -> Tuple['Action', Optional[float]]:
        raise NotImplementedError

class GlobalScriptController(BaseController):
    '''
    A controller that follows a predefined script of (player_name, action, amount).
    Useful for testing game logic.
    '''
    def __init__(self, script: list[Tuple[str, 'Action', Optional[float]]]):
        self.script = script.copy()
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
    
    def decide(self, player, game_state, **kwargs) -> Tuple['Action', Optional[float]]:
        if not self.script:
            raise RuntimeError('No more scripted actions available.')
        
        next_player_name, action, amount = self.script.pop(0)
        if next_player_name != player.name:
            raise ValueError(f'Script mismatch: expected {next_player_name}, got {player.name}')
        
        self.logger.info(f'{player.name} decides... action: {action} amount: {amount}')
        return action, amount

        