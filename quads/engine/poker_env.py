"""
PokerEnv - Gym-like environment wrapper for poker hands.

This module provides a clean interface for agents to interact with poker hands
through a standard reset/step/valid_actions API, similar to OpenAI Gym environments.
"""

import sqlite3
from typing import Any

from .action_data import ActionDecision, GameStateSnapshot, ValidActions
from .agent import Agent
from .enums import ActionType, Phase
from .hand import Hand
from .money import Cents, to_cents
from .observation import ObservationBuilder, ObservationSchema
from .player import Player
from .rules_engine import RulesEngine


class PokerEnv:
    """
    Gym-like environment wrapper for poker hands.
    
    Provides a clean interface for agents to interact with poker hands through
    standard reset/step/valid_actions methods, returning (obs, reward, done, info).
    """
    
    def __init__(self, 
                 players: list[Player], 
                 hand_id: int,
                 deck,
                 dealer_index: int,
                 game_session_id: int,
                 conn: sqlite3.Connection,
                 small_blind: float = 0.25,
                 big_blind: float = 0.50,
                 agents: dict[int, Agent] | None = None,
                 script: dict | None = None):
        """
        Initialize PokerEnv.
        
        Args:
            players: List of players in the hand
            hand_id: Unique identifier for this hand
            deck: Deck instance for dealing cards
            dealer_index: Index of dealer button
            game_session_id: Session identifier
            conn: Database connection
            small_blind: Small blind amount
            big_blind: Big blind amount
            agents: Optional dict mapping player_id -> Agent
            script: Optional script dict for scripted hands
        """
        self.players = players
        self.hand_id = hand_id
        self.deck = deck
        self.dealer_index = dealer_index
        self.game_session_id = game_session_id
        self.conn = conn
        self.small_blind = small_blind
        self.big_blind = big_blind
        self.agents = agents or {}
        self.script = script
        
        # Initialize components
        self.hand = None
        self.rules_engine = RulesEngine(small_blind, big_blind)
        self.observation_builder = ObservationBuilder(small_blind, big_blind)
        
        # Environment state
        self.current_player_id = None
        self.done = False
        self.info = {}
        
    def reset(self) -> tuple[ObservationSchema, dict[str, Any]]:
        """
        Reset the environment and start a new hand.
        
        Returns:
            Tuple of (initial_observation, info_dict)
        """
        # Create new hand instance
        self.hand = Hand(
            players=self.players,
            id=self.hand_id,
            deck=self.deck,
            dealer_index=self.dealer_index,
            game_session_id=self.game_session_id,
            conn=self.conn,
            script=self.script,
            small_blind=self.small_blind,
            big_blind=self.big_blind,
            agents=self.agents
        )
        
        # Reset agent states
        for agent in self.agents.values():
            agent.reset()
        
        # Initialize hand (deal cards, post blinds, etc.)
        self.hand.play()
        
        # Reset environment state
        self.done = False
        self.info = {
            'hand_id': self.hand_id,
            'phase': self.hand.phase,
            'pot': self.hand.pot,
            'players_remaining': len([p for p in self.players if not p.has_folded])
        }
        
        # Get initial observation for first acting player
        initial_obs = self._get_current_observation()
        
        return initial_obs, self.info
    
    def step(self, action: ActionType, amount: Cents | None = None) -> tuple[ObservationSchema, float, bool, dict[str, Any]]:
        """
        Execute an action and return next observation, reward, done, info.
        
        Args:
            action: Action type to execute
            amount: Optional amount for raise/bet actions
            
        Returns:
            Tuple of (observation, reward, done, info)
        """
        if self.done:
            raise RuntimeError("Cannot step in done environment. Call reset() first.")
        
        if self.hand is None:
            raise RuntimeError("Environment not initialized. Call reset() first.")
        
        # Get current acting player
        current_player = self._get_current_acting_player()
        if current_player is None:
            # Hand is over
            self.done = True
            return self._get_final_observation(), 0.0, True, self.info
        
        # Create action decision
        decision = ActionDecision(
            player_id=current_player.id,
            action_type=action,
            amount=amount or 0
        )
        
        # Apply action through rules engine
        current_state = self._get_game_state_snapshot()
        new_state, applied_action = self.rules_engine.apply_action(current_state, decision)
        
        # Update hand state based on applied action
        self._update_hand_from_applied_action(applied_action)
        
        # Check if hand is done
        remaining_players = [p for p in self.players if not p.has_folded]
        if len(remaining_players) <= 1:
            self.done = True
            reward = self._calculate_final_reward(current_player)
            return self._get_final_observation(), reward, True, self.info
        
        # Get next observation
        next_obs = self._get_current_observation()
        
        # Calculate reward (0 for non-terminal states)
        reward = 0.0
        
        # Update info
        self.info.update({
            'phase': self.hand.phase,
            'pot': self.hand.pot,
            'players_remaining': len(remaining_players),
            'last_action': {
                'player_id': current_player.id,
                'action': action.value,
                'amount': amount
            }
        })
        
        return next_obs, reward, self.done, self.info
    
    def valid_actions(self, player_id: int | None = None) -> ValidActions:
        """
        Get valid actions for a player.
        
        Args:
            player_id: Player ID to get actions for. If None, uses current acting player.
            
        Returns:
            ValidActions object with available actions
        """
        if self.hand is None:
            raise RuntimeError("Environment not initialized. Call reset() first.")
        
        if player_id is None:
            current_player = self._get_current_acting_player()
            if current_player is None:
                raise RuntimeError("No current acting player")
            player_id = current_player.id
        
        state = self._get_game_state_snapshot(player_id)
        return self.rules_engine.get_valid_actions(state, player_id)
    
    def get_agent_action(self, player_id: int) -> tuple[ActionType, float | None]:
        """
        Get action from agent for a specific player.
        
        Args:
            player_id: ID of player to get action for
            
        Returns:
            Tuple of (action_type, confidence)
        """
        if player_id not in self.agents:
            raise ValueError(f"No agent found for player {player_id}")
        
        agent = self.agents[player_id]
        obs = self._get_observation_for_player(player_id)
        valid_actions = self.valid_actions(player_id)
        
        return agent.act(obs, valid_actions)
    
    def _get_current_observation(self) -> ObservationSchema:
        """Get observation for the current acting player."""
        current_player = self._get_current_acting_player()
        if current_player is None:
            # Return empty observation if no current player
            return self._get_empty_observation()
        
        return self._get_observation_for_player(current_player.id)
    
    def _get_observation_for_player(self, player_id: int) -> ObservationSchema:
        """Get observation for a specific player."""
        state = self._get_game_state_snapshot(player_id)
        return self.observation_builder.build_observation(state, player_id)
    
    def _get_empty_observation(self) -> ObservationSchema:
        """Get empty observation when no player is acting."""
        # Create minimal state for empty observation
        empty_state = GameStateSnapshot(
            hand_id=self.hand_id,
            phase=Phase.SHOWDOWN,
            pot_cents=0,
            community_cards=[],
            players=[],
            highest_bet=0,
            last_raise_increment=0,
            last_aggressor_seat=None,
            street_number=0,
            acted_this_round={},
            committed_this_round={}
        )
        return self.observation_builder.build_observation(empty_state, 0)
    
    def _get_final_observation(self) -> ObservationSchema:
        """Get final observation when hand is complete."""
        return self._get_empty_observation()
    
    def _get_current_acting_player(self) -> Player | None:
        """Get the current acting player."""
        # This is a simplified implementation
        # In a full implementation, you'd track the betting order properly
        for player in self.players:
            if not player.has_folded and not player.all_in:
                return player
        return None
    
    def _get_game_state_snapshot(self, player_id: int | None = None) -> GameStateSnapshot:
        """Convert Hand state to GameStateSnapshot."""
        if self.hand is None:
            raise RuntimeError("Hand not initialized")
        
        # Convert community cards
        community_cards = []
        if self.hand.community_cards:
            from quads.deuces.card import Card
            community_cards = [Card.int_to_str(c) for c in self.hand.community_cards]
        
        # Convert players to dict format
        players_data = []
        for player in self.players:
            # Convert hole cards to strings - only show for the requesting player
            hole_cards = None
            if player.hole_cards and (player_id is None or player.id == player_id):
                from quads.deuces.card import Card
                hole_cards = [Card.int_to_str(c) if isinstance(c, int) else c for c in player.hole_cards]
            
            players_data.append({
                'id': player.id,
                'name': player.name,
                'stack': player.stack,
                'position': str(player.position) if player.position else None,
                'hole_cards': hole_cards,
                'has_folded': player.has_folded,
                'is_all_in': player.all_in,
                'current_bet': player.current_bet,
                'round_contrib': player.round_contrib,
                'hand_contrib': player.hand_contrib
            })
        
        return GameStateSnapshot(
            hand_id=self.hand.id,
            phase=self.hand.phase,
            pot_cents=to_cents(self.hand.pot),
            community_cards=community_cards,
            players=players_data,
            highest_bet=self.hand.highest_bet,
            last_raise_increment=self.hand.last_full_raise_increment,
            last_aggressor_seat=self.hand.last_aggressor.value if self.hand.last_aggressor else None,
            street_number=self.hand.phase.value,
            acted_this_round={p.id: p.has_acted for p in self.players},
            committed_this_round={p.id: p.round_contrib for p in self.players}
        )
    
    def _update_hand_from_applied_action(self, applied_action) -> None:
        """Update hand state based on applied action."""
        # This is a simplified implementation
        # In a full implementation, you'd properly update the hand state
        # based on the applied action
        pass
    
    def _calculate_final_reward(self, player: Player) -> float:
        """Calculate final reward for a player."""
        # Simplified reward calculation
        # In a full implementation, you'd calculate based on pot winnings
        if player.has_folded:
            return -1.0
        else:
            return 1.0  # Winner gets positive reward
