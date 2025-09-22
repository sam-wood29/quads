"""
Agent Interface - Clean plug-and-play for different agent types.

This module provides a unified interface for all agent types (human, scripted, bot, RL)
to interact with the poker engine through a consistent API.
"""

from abc import ABC, abstractmethod
from typing import Any

from .action_data import ValidActions
from .enums import ActionType
from .observation import ObservationSchema


class Agent(ABC):
    """
    Base class for all poker agents.
    
    Provides a clean interface for agents to make decisions based on observations
    and valid actions, returning both the action type and optional confidence/score.
    """
    
    @abstractmethod
    def act(self, obs: ObservationSchema, valid_actions: ValidActions) -> tuple[ActionType, float | None]:
        """
        Make an action decision based on observation and valid actions.
        
        Args:
            obs: Current observation of the game state
            valid_actions: Available actions the agent can take
            
        Returns:
            Tuple of (action_type, confidence_score)
            - action_type: The action to take
            - confidence_score: Optional confidence/probability score (0.0-1.0)
        """
        pass
    
    def act_with_context(self, obs: ObservationSchema, valid_actions: ValidActions, 
                        game_state: dict[str, Any] | None = None) -> tuple[ActionType, float | None]:
        """
        Make an action decision with additional game state context.
        
        This method allows agents to access raw game state data (like hole cards)
        that isn't available in the observation schema. Default implementation
        delegates to the standard act() method.
        
        Args:
            obs: Current observation of the game state
            valid_actions: Available actions the agent can take
            game_state: Additional game state context (hole cards, board, etc.)
            
        Returns:
            Tuple of (action_type, confidence_score)
        """
        return self.act(obs, valid_actions)
    
    def reset(self) -> None:
        """
        Reset agent state between hands.
        Override in subclasses if needed.
        """
        pass


class HumanAgent(Agent):
    """
    Human agent that prompts for input via console.
    
    This agent will display the current game state and prompt the human
    player to make a decision.
    """
    
    def __init__(self, player_id: int):
        self.player_id = player_id
    
    def act(self, obs: ObservationSchema, valid_actions: ValidActions) -> tuple[ActionType, float | None]:
        """
        Prompt human player for action via console input.
        In test mode, automatically fold to avoid blocking.
        """
        print(f"\n--- Player {self.player_id} Action ---")
        print(f"Phase: {obs.street_number}")
        print(f"Pot: {obs.pot_in_bb:.2f} BB")
        print(f"Stack: {obs.hero_stack_in_bb:.2f} BB")
        print(f"Amount to call: {obs.amount_to_call_in_bb:.2f} BB")
        
        if obs.pf_hand_class:
            print(f"Hole cards: {obs.pf_hand_class}")
        
        print(f"\nValid actions: {[action.value for action in valid_actions.actions]}")
        
        if valid_actions.raise_amounts:
            print(f"Raise amounts: {[amount/100 for amount in valid_actions.raise_amounts]}")
        
        # In test mode, automatically fold to avoid blocking on input
        import sys
        if not sys.stdin.isatty():
            print("Test mode: automatically folding")
            return ActionType.FOLD, 1.0
        
        while True:
            try:
                action_input = input("Enter action (fold/check/call/raise): ").strip().lower()
                
                if action_input == "fold" and ActionType.FOLD in valid_actions.actions:
                    return ActionType.FOLD, 1.0
                elif action_input == "check" and ActionType.CHECK in valid_actions.actions:
                    return ActionType.CHECK, 1.0
                elif action_input == "call" and ActionType.CALL in valid_actions.actions:
                    return ActionType.CALL, 1.0
                elif action_input == "raise" and ActionType.RAISE in valid_actions.actions:
                    if not valid_actions.raise_amounts:
                        print("No raise amounts available")
                        continue
                    
                    amount_input = input(f"Enter raise amount (available: {[a/100 for a in valid_actions.raise_amounts]}): ")
                    amount_cents = int(float(amount_input) * 100)
                    
                    if amount_cents in valid_actions.raise_amounts:
                        return ActionType.RAISE, 1.0
                    else:
                        print(f"Invalid raise amount. Must be one of: {[a/100 for a in valid_actions.raise_amounts]}")
                        continue
                else:
                    print("Invalid action or action not available")
                    continue
                    
            except (ValueError, KeyboardInterrupt):
                print("Invalid input. Please try again.")
                continue


class ScriptedAgent(Agent):
    """
    Deterministic agent that follows a pre-defined action sequence.
    
    This agent replays a scripted sequence of actions, useful for testing
    and reproducing specific game scenarios.
    """
    
    def __init__(self, actions: list[dict], player_id: int):
        """
        Initialize ScriptedAgent.
        
        Args:
            actions: List of action dicts with "type" and optional "amount"
            player_id: ID of the player this agent represents
        """
        self.actions = actions
        self.player_id = player_id
        self.action_index = 0
    
    def act(self, obs: ObservationSchema, valid_actions: ValidActions) -> tuple[ActionType, float | None]:
        """
        Get next action from script.
        """
        if self.action_index >= len(self.actions):
            raise RuntimeError(f"ScriptedAgent for player {self.player_id} ran out of actions")
        
        action_dict = self.actions[self.action_index]
        self.action_index += 1
        
        # Parse action type
        action_type_str = action_dict["type"].lower()
        match action_type_str:
            case "check":
                action_type = ActionType.CHECK
            case "fold":
                action_type = ActionType.FOLD
            case "call":
                action_type = ActionType.CALL
            case "raise":
                action_type = ActionType.RAISE
            case "bet":
                action_type = ActionType.RAISE  # bet becomes raise in the system
            case _:
                raise ValueError(f"Unknown action type: {action_type_str}")
        
        # Validate that the action is available
        if action_type not in valid_actions.actions:
            # Fall back to an available action if the scripted action is not valid
            if ActionType.CHECK in valid_actions.actions:
                print(f"Scripted action {action_type} not available, falling back to CHECK")
                return ActionType.CHECK, 0.8
            elif ActionType.FOLD in valid_actions.actions:
                print(f"Scripted action {action_type} not available, falling back to FOLD")
                return ActionType.FOLD, 0.8
            else:
                raise ValueError(f"Scripted action {action_type} not available in valid actions: {valid_actions.actions}")
        
        return action_type, 1.0
    
    def reset(self) -> None:
        """Reset to beginning of script."""
        self.action_index = 0


class RuleBasedAgent(Agent):
    """
    Stub for rule-based agent implementation.
    
    This agent will implement basic poker strategy rules.
    Currently just a placeholder for future implementation.
    """
    
    def __init__(self, player_id: int):
        self.player_id = player_id
    
    def act(self, obs: ObservationSchema, valid_actions: ValidActions) -> tuple[ActionType, float | None]:
        """
        Stub implementation - always folds.
        """
        # TODO: Implement basic poker strategy rules
        # For now, just fold to avoid breaking the system
        if ActionType.FOLD in valid_actions.actions:
            return ActionType.FOLD, 0.5
        else:
            # If can't fold, check if available
            if ActionType.CHECK in valid_actions.actions:
                return ActionType.CHECK, 0.5
            else:
                # Last resort - call
                return ActionType.CALL, 0.3
