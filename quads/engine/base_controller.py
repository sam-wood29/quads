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
    def __init__(self, script: list[Tuple[str, 'Action', Optional[float]]], 
                 test_hooks: Optional[dict] = None):
        self.script = script.copy()
        self.test_hooks = test_hooks or {}
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
    
    def decide(self, player, game_state, **kwargs) -> Tuple['Action', Optional[float]]:
        if not self.script:
            raise RuntimeError('No more scripted actions available.')
        
        next_player_name, action, amount = self.script.pop(0)
        if next_player_name != player.name:
            raise ValueError(f'Script mismatch: expected {next_player_name}, got {player.name}')
        
        # Call pre-action hook if exists
        if 'pre_action' in self.test_hooks:
            self.test_hooks['pre_action'](player, action, amount, game_state)
        
        self.logger.info(f'{player.name} decides... action: {action} amount: {amount}')
        return action, amount

class ManualInputController(BaseController):
    """
    Controller for human/manual input via the terminal.
    Prompts the user for action and amount.
    """
    def decide(self, player, game_state, **kwargs):
        valid_actions = game_state['valid_actions']['actions']
        min_raise = game_state['valid_actions'].get('min_raise')
        max_raise = game_state['valid_actions'].get('max_raise')
        print(f"\n--- {player.name}'s turn ---")
        print(f"Stack: {player.stack}")
        print(f"Position: {player.position}")
        print(f"Community cards: {game_state['community_cards']}")
        print(f"Your hole cards: {player.hole_cards}")
        print(f"Pot: {game_state['pot']}")
        print(f"Amount to call: {game_state['amount_to_call']}")
        print(f"Valid actions: {[a.name for a in valid_actions]}")
        if min_raise is not None and max_raise is not None:
            print(f"Raise range: {min_raise} to {max_raise}")

        # Prompt for action
        while True:
            action_input = input("Choose action: ").strip().upper()
            try:
                action = next(a for a in valid_actions if a.name == action_input)
            except StopIteration:
                print("Invalid action. Try again.")
                continue

            amount = None
            if action in [Action.RAISE, Action.BET]:
                while True:
                    try:
                        amount_input = input(f"Enter amount ({min_raise} - {max_raise}): ").strip()
                        amount = float(amount_input)
                        if min_raise <= amount <= max_raise:
                            break
                        else:
                            print("Amount out of range.")
                    except Exception:
                        print("Invalid amount. Try again.")
            break

        return action, amount

        