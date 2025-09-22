"""
Observation Builder - Canonical feature extraction for ML training.

This module provides a single source of truth for converting poker game state
into fixed-size observation vectors for machine learning training.

Key principles:
- No information leakage (no opponent hole cards)
- Fixed schema for reproducibility
- Comprehensive feature coverage
- Consistent data types
"""

from dataclasses import dataclass
from typing import Any

import numpy as np

from .action_data import GameStateSnapshot
from .enums import Phase
from .player import Position


@dataclass(frozen=True)
class ObservationSchema:
    """Fixed schema for observation vectors."""
    
    # Core game state (8 features)
    street_one_hot: np.ndarray  # 5 elements (deal, preflop, flop, turn, river)
    players_remaining: int  # 1 element
    hero_position_one_hot: np.ndarray  # 10 elements (all positions)
    
    # Pot and betting metrics (4 features)
    pot_in_bb: float  # 1 element
    amount_to_call_in_bb: float  # 1 element
    pot_odds: float  # 1 element
    bet_to_call_ratio: float  # 1 element
    
    # Stack metrics (3 features)
    hero_stack_in_bb: float  # 1 element
    effective_stack_in_bb: float  # 1 element
    spr: float  # 1 element (Stack-to-Pot Ratio)
    
    # Preflop hand features (8 features)
    is_pair: int  # 1 element (0/1)
    is_suited: int  # 1 element (0/1)
    gap: int  # 1 element
    high_rank: int  # 1 element (2-14)
    low_rank: int  # 1 element (2-14)
    chen_score: float  # 1 element
    pf_hand_class: str  # 1 element (e.g., "AKs", "72o")
    hand_strength_percentile: float  # 1 element (0-1)
    
    # Betting history flags (4 features)
    raises_this_street: int  # 1 element
    last_raise_increment_in_bb: float  # 1 element
    is_aggressor: int  # 1 element (0/1)
    has_position: int  # 1 element (0/1)
    
    # Board texture (6 features)
    board_paired: int  # 1 element (0/1)
    board_monotone: int  # 1 element (0/1)
    board_two_tone: int  # 1 element (0/1)
    straighty_index: float  # 1 element (0-1)
    top_board_rank: int  # 1 element (2-14)
    board_coordination: float  # 1 element (0-1)
    
    # Additional features (4 features)
    players_acted_this_street: int  # 1 element
    street_number: int  # 1 element
    is_all_in: int  # 1 element (0/1)
    stack_depth_category: int  # 1 element (0-4: shallow, medium, deep, very_deep)
    
    @property
    def total_features(self) -> int:
        """Total number of features in the observation vector."""
        return (5 + 1 + 10 + 4 + 3 + 8 + 4 + 6 + 4)  # 45 features total
    
    def to_vector(self) -> np.ndarray:
        """Convert observation to fixed-size numpy array."""
        features = []
        
        # Core game state
        features.extend(self.street_one_hot)  # 5
        features.append(self.players_remaining)  # 1
        features.extend(self.hero_position_one_hot)  # 10
        
        # Pot and betting metrics
        features.extend([
            self.pot_in_bb,
            self.amount_to_call_in_bb,
            self.pot_odds,
            self.bet_to_call_ratio
        ])  # 4
        
        # Stack metrics
        features.extend([
            self.hero_stack_in_bb,
            self.effective_stack_in_bb,
            self.spr
        ])  # 3
        
        # Preflop hand features
        features.extend([
            self.is_pair,
            self.is_suited,
            self.gap,
            self.high_rank,
            self.low_rank,
            self.chen_score,
            hash(self.pf_hand_class) % 1000,  # Convert string to int
            self.hand_strength_percentile
        ])  # 8
        
        # Betting history flags
        features.extend([
            self.raises_this_street,
            self.last_raise_increment_in_bb,
            self.is_aggressor,
            self.has_position
        ])  # 4
        
        # Board texture
        features.extend([
            self.board_paired,
            self.board_monotone,
            self.board_two_tone,
            self.straighty_index,
            self.top_board_rank,
            self.board_coordination
        ])  # 6
        
        # Additional features
        # Convert street_number to integer based on phase
        street_number_map = {'deal': 0, 'preflop': 1, 'flop': 2, 'turn': 3, 'river': 4, 'showdown': 5}
        street_number_int = street_number_map.get(self.street_number, 0) if isinstance(self.street_number, str) else self.street_number
        
        features.extend([
            self.players_acted_this_street,
            street_number_int,
            self.is_all_in,
            self.stack_depth_category
        ])  # 4
        
        return np.array(features, dtype=np.float32)


class ObservationBuilder:
    """Builds observation vectors from game state."""
    
    def __init__(self, small_blind: float = 0.25, big_blind: float = 0.50):
        self.small_blind = small_blind
        self.big_blind = big_blind
        self.big_blind_cents = int(big_blind * 100)
        
        # Position mapping for one-hot encoding
        self.position_to_index = {
            Position.UTG: 0, Position.UTG1: 1, Position.UTG2: 2,
            Position.LJ: 3, Position.MP: 4, Position.HJ: 5,
            Position.CO: 6, Position.BUTTON: 7, Position.SB: 8, Position.BB: 9
        }
        
        # Street mapping for one-hot encoding
        self.street_to_index = {
            Phase.DEAL: 0, Phase.PREFLOP: 1, Phase.FLOP: 2,
            Phase.TURN: 3, Phase.RIVER: 4
        }
    
    def build_observation(self, state: GameStateSnapshot, player_id: int) -> ObservationSchema:
        """
        Build observation for a specific player.
        
        Args:
            state: Current game state snapshot
            player_id: ID of the player to build observation for
            
        Returns:
            ObservationSchema with all features populated
        """
        # Validate no information leakage
        self._validate_no_leakage(state, player_id)
        
        # Get hero player data
        hero = self._get_player(state, player_id)
        if not hero:
            raise ValueError(f"Player {player_id} not found in state")
        
        # Extract all feature categories
        core_features = self._extract_core_features(state, hero)
        pot_betting_features = self._extract_pot_betting_features(state, hero)
        stack_features = self._extract_stack_features(state, hero)
        preflop_features = self._extract_preflop_features(state, hero)
        betting_history_features = self._extract_betting_history_features(state, hero)
        board_texture_features = self._extract_board_texture_features(state)
        additional_features = self._extract_additional_features(state, hero)
        
        return ObservationSchema(
            **core_features,
            **pot_betting_features,
            **stack_features,
            **preflop_features,
            **betting_history_features,
            **board_texture_features,
            **additional_features
        )
    
    def _validate_no_leakage(self, state: GameStateSnapshot, player_id: int) -> None:
        """Validate that no opponent hole cards are leaked."""
        hero_found = False
        for player in state.players:
            if player['id'] == player_id:
                hero_found = True
            elif player.get('hole_cards'):
                raise ValueError("Information leakage detected: opponent hole cards present")
        
        if not hero_found:
            raise ValueError(f"Player {player_id} not found in state")
    
    def _get_player(self, state: GameStateSnapshot, player_id: int) -> dict[str, Any] | None:
        """Get player data from state."""
        for player in state.players:
            if player['id'] == player_id:
                return player
        return None
    
    def _extract_core_features(self, state: GameStateSnapshot, hero: dict[str, Any]) -> dict[str, Any]:
        """Extract core game state features."""
        # Street one-hot encoding
        street_one_hot = np.zeros(5, dtype=np.float32)
        street_idx = self.street_to_index.get(Phase(state.phase), 0)
        street_one_hot[street_idx] = 1.0
        
        # Players remaining (not folded)
        players_remaining = sum(1 for p in state.players if not p.get('has_folded', False))
        
        # Hero position one-hot encoding
        hero_position_one_hot = np.zeros(10, dtype=np.float32)
        hero_position = hero.get('position')
        if hero_position and hero_position in self.position_to_index:
            pos_idx = self.position_to_index[hero_position]
            hero_position_one_hot[pos_idx] = 1.0
        
        return {
            'street_one_hot': street_one_hot,
            'players_remaining': players_remaining,
            'hero_position_one_hot': hero_position_one_hot
        }
    
    def _extract_pot_betting_features(self, state: GameStateSnapshot, hero: dict[str, Any]) -> dict[str, Any]:
        """Extract pot and betting metrics."""
        pot_in_bb = state.pot_cents / self.big_blind_cents
        
        # Amount to call
        hero_current_bet = hero.get('current_bet', 0)
        amount_to_call_cents = max(0, state.highest_bet - hero_current_bet)
        amount_to_call_in_bb = amount_to_call_cents / self.big_blind_cents
        
        # Pot odds
        pot_odds = 0.0
        if amount_to_call_cents > 0:
            pot_odds = amount_to_call_cents / (state.pot_cents + amount_to_call_cents)
        
        # Bet to call ratio
        bet_to_call_ratio = 0.0
        if amount_to_call_cents > 0:
            bet_to_call_ratio = amount_to_call_cents / self.big_blind_cents
        
        return {
            'pot_in_bb': pot_in_bb,
            'amount_to_call_in_bb': amount_to_call_in_bb,
            'pot_odds': pot_odds,
            'bet_to_call_ratio': bet_to_call_ratio
        }
    
    def _extract_stack_features(self, state: GameStateSnapshot, hero: dict[str, Any]) -> dict[str, Any]:
        """Extract stack-related metrics."""
        hero_stack_in_bb = hero.get('stack', 0) / self.big_blind_cents
        
        # Effective stack (min of hero and deepest opponent)
        opponent_stacks = [
            p.get('stack', 0) for p in state.players 
            if p['id'] != hero['id'] and not p.get('has_folded', False)
        ]
        if opponent_stacks:
            effective_stack_cents = min(hero.get('stack', 0), max(opponent_stacks))
        else:
            # No opponents, effective stack is hero's stack
            effective_stack_cents = hero.get('stack', 0)
        effective_stack_in_bb = effective_stack_cents / self.big_blind_cents
        
        # SPR (Stack-to-Pot Ratio)
        spr = 0.0
        if state.pot_cents > 0:
            spr = effective_stack_cents / state.pot_cents
        
        return {
            'hero_stack_in_bb': hero_stack_in_bb,
            'effective_stack_in_bb': effective_stack_in_bb,
            'spr': spr
        }
    
    def _extract_preflop_features(self, state: GameStateSnapshot, hero: dict[str, Any]) -> dict[str, Any]:
        """Extract preflop hand features."""
        # Get hole cards from hero's hand contribution data
        hole_cards = hero.get('hole_cards')
        
        if not hole_cards or len(hole_cards) != 2:
            # Return default values if no hole cards
            return {
                'is_pair': 0,
                'is_suited': 0,
                'gap': 0,
                'high_rank': 2,
                'low_rank': 2,
                'chen_score': 0.0,
                'pf_hand_class': 'XX',
                'hand_strength_percentile': 0.0
            }
        
        # Parse hole cards
        card1, card2 = hole_cards[0], hole_cards[1]
        
        # Extract ranks and suits
        rank1 = self._card_to_rank(card1)
        rank2 = self._card_to_rank(card2)
        suit1 = self._card_to_suit(card1)
        suit2 = self._card_to_suit(card2)
        
        # Calculate features
        is_pair = 1 if rank1 == rank2 else 0
        is_suited = 1 if suit1 == suit2 else 0
        high_rank = max(rank1, rank2)
        low_rank = min(rank1, rank2)
        gap = abs(rank1 - rank2)
        
        # Chen score calculation
        chen_score = self._calculate_chen_score(rank1, rank2, is_pair, is_suited, gap)
        
        # Hand class (e.g., "AKs", "72o")
        pf_hand_class = self._get_hand_class(high_rank, low_rank, is_suited)
        
        # Hand strength percentile (0-1)
        hand_strength_percentile = self._get_hand_strength_percentile(high_rank, low_rank, is_pair, is_suited)
        
        return {
            'is_pair': is_pair,
            'is_suited': is_suited,
            'gap': gap,
            'high_rank': high_rank,
            'low_rank': low_rank,
            'chen_score': chen_score,
            'pf_hand_class': pf_hand_class,
            'hand_strength_percentile': hand_strength_percentile
        }
    
    def _extract_betting_history_features(self, state: GameStateSnapshot, hero: dict[str, Any]) -> dict[str, Any]:
        """Extract betting history flags."""
        # Count raises this street (simplified - would need more detailed tracking)
        raises_this_street = 0  # TODO: Implement proper raise counting
        
        # Last raise increment
        last_raise_increment_in_bb = state.last_raise_increment / self.big_blind_cents
        
        # Is aggressor (made the last raise)
        is_aggressor = 1 if state.last_aggressor_seat == hero['id'] else 0
        
        # Has position (simplified - would need proper position analysis)
        has_position = self._has_position(hero.get('position'))
        
        return {
            'raises_this_street': raises_this_street,
            'last_raise_increment_in_bb': last_raise_increment_in_bb,
            'is_aggressor': is_aggressor,
            'has_position': has_position
        }
    
    def _extract_board_texture_features(self, state: GameStateSnapshot) -> dict[str, Any]:
        """Extract board texture analysis."""
        board_cards = state.community_cards
        
        if not board_cards:
            return {
                'board_paired': 0,
                'board_monotone': 0,
                'board_two_tone': 0,
                'straighty_index': 0.0,
                'top_board_rank': 2,
                'board_coordination': 0.0
            }
        
        # Analyze board texture
        ranks = [self._card_to_rank(card) for card in board_cards]
        suits = [self._card_to_suit(card) for card in board_cards]
        
        # Paired board
        board_paired = 1 if len(set(ranks)) < len(ranks) else 0
        
        # Suit analysis
        suit_counts = {}
        for suit in suits:
            suit_counts[suit] = suit_counts.get(suit, 0) + 1
        
        board_monotone = 1 if max(suit_counts.values()) >= 3 else 0
        board_two_tone = 1 if len(suit_counts) == 2 else 0
        
        # Straighty index (how connected the board is)
        straighty_index = self._calculate_straighty_index(ranks)
        
        # Top board rank
        top_board_rank = max(ranks) if ranks else 2
        
        # Board coordination (how coordinated/connected the board is)
        board_coordination = self._calculate_board_coordination(ranks, suits)
        
        return {
            'board_paired': board_paired,
            'board_monotone': board_monotone,
            'board_two_tone': board_two_tone,
            'straighty_index': straighty_index,
            'top_board_rank': top_board_rank,
            'board_coordination': board_coordination
        }
    
    def _extract_additional_features(self, state: GameStateSnapshot, hero: dict[str, Any]) -> dict[str, Any]:
        """Extract additional contextual features."""
        # Players acted this street
        players_acted_this_street = sum(state.acted_this_round.values())
        
        # Street number
        street_number = state.street_number
        
        # Is all-in
        is_all_in = 1 if hero.get('is_all_in', False) else 0
        
        # Stack depth category
        hero_stack_bb = hero.get('stack', 0) / self.big_blind_cents
        stack_depth_category = self._get_stack_depth_category(hero_stack_bb)
        
        return {
            'players_acted_this_street': players_acted_this_street,
            'street_number': street_number,
            'is_all_in': is_all_in,
            'stack_depth_category': stack_depth_category
        }
    
    # Helper methods
    def _card_to_rank(self, card: str) -> int:
        """Convert card string to rank (2-14, where 14=Ace)."""
        rank_map = {'2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8,
                   '9': 9, 'T': 10, 'J': 11, 'Q': 12, 'K': 13, 'A': 14}
        return rank_map.get(card[0], 2)
    
    def _card_to_suit(self, card: str) -> str:
        """Extract suit from card string."""
        return card[1] if len(card) > 1 else 's'
    
    def _calculate_chen_score(self, rank1: int, rank2: int, is_pair: int, is_suited: int, gap: int) -> float:
        """Calculate Chen score for hand strength."""
        chen_values = {14: 10, 13: 8, 12: 7, 11: 6, 10: 5, 9: 4.5, 8: 4, 7: 3.5,
                      6: 3, 5: 2.5, 4: 2, 3: 1.5, 2: 1}
        
        high = max(rank1, rank2)
        score = chen_values.get(high, 1)
        
        if is_pair:
            score = max(score * 2, 5)
        if is_suited:
            score += 2
        if gap == 0:
            pass
        elif gap == 1:
            score += 1
        elif gap == 2:
            score += 0.5
        else:
            score -= (gap - 2)
        
        return max(score, 0.5)
    
    def _get_hand_class(self, high_rank: int, low_rank: int, is_suited: int) -> str:
        """Get hand class string (e.g., 'AKs', '72o')."""
        rank_chars = {2: '2', 3: '3', 4: '4', 5: '5', 6: '6', 7: '7', 8: '8',
                     9: '9', 10: 'T', 11: 'J', 12: 'Q', 13: 'K', 14: 'A'}
        
        high_char = rank_chars.get(high_rank, '2')
        low_char = rank_chars.get(low_rank, '2')
        suit_char = 's' if is_suited else 'o'
        
        return f"{high_char}{low_char}{suit_char}"
    
    def _get_hand_strength_percentile(self, high_rank: int, low_rank: int, is_pair: int, is_suited: int) -> float:
        """Get hand strength percentile (0-1)."""
        # Simplified percentile calculation
        # In practice, this would use a lookup table of all 169 possible hands
        base_strength = (high_rank + low_rank) / 28.0  # Normalize to 0-1
        if is_pair:
            base_strength *= 1.5
        if is_suited:
            base_strength *= 1.1
        
        return min(base_strength, 1.0)
    
    def _has_position(self, position: str | None) -> int:
        """Determine if player has position (simplified)."""
        if not position:
            return 0
        
        # Simplified: button, CO, HJ have position
        position_ranks = {
            'button': 1, 'co': 1, 'hj': 1,
            'mp': 0, 'lj': 0, 'utg': 0, 'utg1': 0, 'utg2': 0,
            'sb': 0, 'bb': 0
        }
        
        return position_ranks.get(position.lower(), 0)
    
    def _calculate_straighty_index(self, ranks: list[int]) -> float:
        """Calculate how 'straighty' the board is (0-1)."""
        if len(ranks) < 2:
            return 0.0
        
        sorted_ranks = sorted(set(ranks))
        max_consecutive = 1
        current_consecutive = 1
        
        for i in range(1, len(sorted_ranks)):
            if sorted_ranks[i] == sorted_ranks[i-1] + 1:
                current_consecutive += 1
                max_consecutive = max(max_consecutive, current_consecutive)
            else:
                current_consecutive = 1
        
        # Normalize to 0-1 (max possible consecutive is 5)
        return max_consecutive / 5.0
    
    def _calculate_board_coordination(self, ranks: list[int], suits: list[str]) -> float:
        """Calculate board coordination (0-1)."""
        if len(ranks) < 2:
            return 0.0
        
        # Count pairs, straights, flushes
        rank_counts = {}
        for rank in ranks:
            rank_counts[rank] = rank_counts.get(rank, 0) + 1
        
        suit_counts = {}
        for suit in suits:
            suit_counts[suit] = suit_counts.get(suit, 0) + 1
        
        # Calculate coordination score
        pairs = sum(1 for count in rank_counts.values() if count > 1)
        max_suit = max(suit_counts.values()) if suit_counts else 0
        
        # Normalize to 0-1
        coordination = (pairs + max_suit) / 8.0
        return min(coordination, 1.0)
    
    def _get_stack_depth_category(self, stack_bb: float) -> int:
        """Categorize stack depth (0-4)."""
        if stack_bb < 20:
            return 0  # Shallow
        elif stack_bb < 50:
            return 1  # Medium
        elif stack_bb < 100:
            return 2  # Deep
        elif stack_bb < 200:
            return 3  # Very deep
        else:
            return 4  # Ultra deep


def build_observation(state: GameStateSnapshot, player_id: int, 
                     small_blind: float = 0.25, big_blind: float = 0.50) -> np.ndarray:
    """
    Convenience function to build observation vector.
    
    Args:
        state: Game state snapshot
        player_id: Player ID to build observation for
        small_blind: Small blind amount
        big_blind: Big blind amount
        
    Returns:
        Fixed-size numpy array observation vector
    """
    builder = ObservationBuilder(small_blind, big_blind)
    observation = builder.build_observation(state, player_id)
    return observation.to_vector()
