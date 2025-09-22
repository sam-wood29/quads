"""
Rule-Based Poker Agent - Block 12 Implementation

A competent baseline agent that uses Monte Carlo equity estimation and
pot odds comparison to make fold/call/raise decisions.

Key features:
- Monte Carlo equity calculation (configurable samples)
- Pot odds-based folding with epsilon threshold
- Value betting and semibluffing with SPR considerations
- Discrete raise amount mapping
- Realistic opponent modeling
"""

import random
from typing import Any

import numpy as np

from quads.deuces.card import Card
from quads.deuces.deck import Deck
from quads.deuces.evaluator import Evaluator

from .action_data import ValidActions
from .agent import Agent
from .enums import ActionType
from .money import Cents
from .observation import ObservationSchema


class RuleBasedAgent(Agent):
    """
    Rule-based poker agent using Monte Carlo equity estimation.
    
    Makes decisions based on:
    1. Monte Carlo equity calculation
    2. Pot odds comparison with epsilon threshold
    3. Value betting and semibluffing heuristics
    4. Stack-to-pot ratio (SPR) considerations
    """
    
    def __init__(self, 
                 player_id: int,
                 epsilon: float = 0.05,
                 mc_samples: int = 5000,
                 value_threshold: float = 0.6,
                 semibluff_threshold: float = 0.3,
                 debug: bool = False,
                 random_seed: int | None = None):
        """
        Initialize rule-based agent.
        
        Args:
            player_id: Player ID for this agent
            epsilon: Fold threshold below pot odds (default 5%)
            mc_samples: Number of Monte Carlo samples for equity calculation
            value_threshold: Minimum equity for value betting
            semibluff_threshold: Minimum equity for semibluffing
            debug: Enable debug logging
            random_seed: Random seed for reproducible decisions
        """
        self.player_id = player_id
        self.epsilon = epsilon
        self.mc_samples = mc_samples
        self.value_threshold = value_threshold
        self.semibluff_threshold = semibluff_threshold
        self.debug = debug
        self.random_seed = random_seed
        
        # Initialize evaluator and random state
        self.evaluator = Evaluator()
        if random_seed is not None:
            random.seed(random_seed)
            np.random.seed(random_seed)
    
    def act(self, obs: ObservationSchema, valid_actions: ValidActions) -> tuple[ActionType, float | None]:
        """
        Make action decision based on observation and valid actions.
        
        Args:
            obs: Current game state observation
            valid_actions: Available actions
            
        Returns:
            Tuple of (action_type, confidence_score)
        """
        return self.act_with_context(obs, valid_actions, None)
    
    def act_with_context(self, obs: ObservationSchema, valid_actions: ValidActions, 
                        game_state: dict[str, Any] | None = None) -> tuple[ActionType, float | None]:
        """
        Make action decision with additional game state context.
        
        Args:
            obs: Current game state observation
            valid_actions: Available actions
            game_state: Additional game state context (hole cards, board, etc.)
            
        Returns:
            Tuple of (action_type, confidence_score)
        """
        if self.debug:
            print("\n=== RuleBasedAgent Decision ===")
            print(f"Player {self.player_id}")
            print(f"Pot: {obs.pot_in_bb:.2f} BB")
            print(f"Amount to call: {obs.amount_to_call_in_bb:.2f} BB")
            print(f"Pot odds: {obs.pot_odds:.3f}")
            print(f"SPR: {obs.spr:.2f}")
            print(f"Hole cards: {obs.pf_hand_class}")
        
        # Extract hole cards and board from game state or observation
        hole_cards = self._extract_hole_cards(obs, game_state)
        board = self._extract_board(obs, game_state)
        
        if hole_cards is None or board is None:
            # Fallback to fold if we can't extract cards
            if self.debug:
                print("Could not extract cards, folding")
            return ActionType.FOLD, 0.0
        
        # Calculate equity via Monte Carlo
        equity = self.estimate_equity(hole_cards, board, obs.players_remaining - 1)
        
        if self.debug:
            print(f"Estimated equity: {equity:.3f}")
            print(f"Fold threshold: {obs.pot_odds - self.epsilon:.3f}")
        
        # Apply decision logic
        action, confidence = self._make_decision(obs, valid_actions, equity)
        
        if self.debug:
            print(f"Decision: {action.value} (confidence: {confidence:.2f})")
        
        return action, confidence
    
    def estimate_equity(self, hole_cards: list[int], board: list[int], num_opponents: int) -> float:
        """
        Estimate hand equity using Monte Carlo simulation.
        
        Args:
            hole_cards: Hero's hole cards as integer representations
            board: Community cards as integer representations
            num_opponents: Number of opponents to simulate
            
        Returns:
            Equity as float between 0.0 and 1.0
        """
        if num_opponents <= 0:
            return 1.0  # No opponents, guaranteed win
        
        # Create deck excluding known cards
        known_cards = set(hole_cards + board)
        remaining_cards = [card for card in Deck.GetFullDeck() if card not in known_cards]
        
        if len(remaining_cards) < num_opponents * 2 + (5 - len(board)):
            # Not enough cards for simulation
            if self.debug:
                print(f"Not enough cards: {len(remaining_cards)} remaining, need {num_opponents * 2 + (5 - len(board))}")
            return 0.0
        
        wins = 0
        ties = 0
        total_samples = 0
        
        # Monte Carlo simulation
        for _ in range(self.mc_samples):
            # Shuffle remaining cards
            shuffled = remaining_cards.copy()
            random.shuffle(shuffled)
            
            # Deal opponent hands
            opponent_hands = []
            card_index = 0
            
            for _ in range(num_opponents):
                if card_index + 1 < len(shuffled):
                    opponent_hands.append([shuffled[card_index], shuffled[card_index + 1]])
                    card_index += 2
                else:
                    break  # Not enough cards
            
            if len(opponent_hands) != num_opponents:
                continue  # Skip this sample if not enough cards
            
            # Determine remaining board cards needed
            board_cards_needed = 5 - len(board)
            if card_index + board_cards_needed > len(shuffled):
                continue  # Skip if not enough cards for board
            
            # Complete the board
            complete_board = board + shuffled[card_index:card_index + board_cards_needed]
            
            # Evaluate all hands
            hero_score = self.evaluator.evaluate(hole_cards, complete_board)
            opponent_scores = [self.evaluator.evaluate(hand, complete_board) for hand in opponent_hands]
            
            # Count wins and ties
            best_opponent_score = min(opponent_scores)  # Lower is better
            
            if hero_score < best_opponent_score:
                wins += 1
            elif hero_score == best_opponent_score:
                ties += 1
            
            total_samples += 1
        
        if total_samples == 0:
            if self.debug:
                print("No valid samples generated")
            return 0.0  # Fallback if no valid samples
        
        # Calculate equity (wins + 0.5 * ties)
        equity = (wins + 0.5 * ties) / total_samples
        
        if self.debug:
            print(f"Equity calculation: {wins} wins, {ties} ties, {total_samples} samples")
        
        return equity
    
    def _make_decision(self, obs: ObservationSchema, valid_actions: ValidActions, equity: float) -> tuple[ActionType, float]:
        """
        Make fold/call/raise decision based on equity and game state.
        
        Args:
            obs: Game state observation
            valid_actions: Available actions
            equity: Estimated hand equity
            
        Returns:
            Tuple of (action_type, confidence)
        """
        fold_threshold = obs.pot_odds - self.epsilon
        
        # Special case: BB min-defense
        if self._is_bb_min_defense(obs, valid_actions):
            if ActionType.CALL in valid_actions.actions:
                return ActionType.CALL, 0.7
        
        # Fold if equity below threshold
        if equity < fold_threshold:
            if ActionType.FOLD in valid_actions.actions:
                return ActionType.FOLD, 1.0
        
        # Determine if we should raise
        should_raise = self._should_raise(obs, equity)
        
        if should_raise and ActionType.RAISE in valid_actions.actions and valid_actions.raise_amounts:
            # Choose raise amount based on equity
            raise_amount = self._choose_raise_amount(obs, valid_actions, equity)
            if raise_amount is not None:
                return ActionType.RAISE, self._calculate_raise_confidence(equity)
        
        # Default to call if available
        if ActionType.CALL in valid_actions.actions:
            return ActionType.CALL, 0.8
        elif ActionType.CHECK in valid_actions.actions:
            return ActionType.CHECK, 0.9
        
        # Fallback to fold
        return ActionType.FOLD, 0.5
    
    def _should_raise(self, obs: ObservationSchema, equity: float) -> bool:
        """
        Determine if we should raise based on equity and SPR.
        
        Args:
            obs: Game state observation
            equity: Hand equity
            
        Returns:
            True if we should raise
        """
        # Value betting: strong equity
        if equity >= self.value_threshold:
            return True
        
        # Semibluffing: decent equity + good SPR
        if equity >= self.semibluff_threshold and obs.spr >= 3.0:
            return True
        
        # Bluffing: very high SPR (rare)
        if obs.spr >= 10.0 and equity >= 0.2:
            return True
        
        return False
    
    def _choose_raise_amount(self, obs: ObservationSchema, valid_actions: ValidActions, equity: float) -> Cents | None:
        """
        Choose raise amount based on equity and available options.
        
        Args:
            obs: Game state observation
            valid_actions: Available actions
            equity: Hand equity
            
        Returns:
            Raise amount in cents, or None if no good option
        """
        if not valid_actions.raise_amounts:
            return None
        
        # Map equity to raise sizing
        if equity >= 0.8:  # Nuts
            # Prefer all-in or pot-sized raise
            for amount in reversed(valid_actions.raise_amounts):
                if amount >= obs.pot_in_bb * 100:  # At least pot-sized
                    return amount
        elif equity >= self.value_threshold:  # Strong value
            # Prefer pot-sized raise
            pot_size_cents = int(obs.pot_in_bb * 100)
            for amount in valid_actions.raise_amounts:
                if abs(amount - pot_size_cents) < pot_size_cents * 0.2:  # Within 20% of pot
                    return amount
        elif equity >= self.semibluff_threshold:  # Semibluff
            # Prefer smaller raises (2.5x or min-raise)
            for amount in valid_actions.raise_amounts:
                if amount <= obs.pot_in_bb * 100 * 2.5:  # At most 2.5x pot
                    return amount
        
        # Fallback to min-raise
        return valid_actions.raise_amounts[0] if valid_actions.raise_amounts else None
    
    def _calculate_raise_confidence(self, equity: float) -> float:
        """Calculate confidence for raise decision based on equity."""
        if equity >= 0.8:
            return 0.95
        elif equity >= self.value_threshold:
            return 0.85
        elif equity >= self.semibluff_threshold:
            return 0.75
        else:
            return 0.65
    
    def _is_bb_min_defense(self, obs: ObservationSchema, valid_actions: ValidActions) -> bool:
        """
        Check if this is a big blind min-defense situation.
        
        Args:
            obs: Game state observation
            valid_actions: Available actions
            
        Returns:
            True if this is BB min-defense
        """
        # Simplified check: small amount to call, early position
        return (obs.amount_to_call_in_bb <= 1.0 and 
                obs.hero_position_one_hot[0] == 1.0)  # BB position
    
    def _extract_hole_cards(self, obs: ObservationSchema, game_state: dict[str, Any] | None = None) -> list[int] | None:
        """
        Extract hole cards from observation or game state.
        
        Args:
            obs: Game state observation
            game_state: Additional game state context
            
        Returns:
            List of hole cards as integers, or None if not available
        """
        # Try to get hole cards from game state first
        if game_state and 'hole_cards' in game_state:
            hole_cards_str = game_state['hole_cards']
            if hole_cards_str and len(hole_cards_str) >= 2:
                try:
                    # Parse hole cards string like "Ah,Kd"
                    cards = hole_cards_str.split(',')
                    if len(cards) == 2:
                        card1_int = Card.new(cards[0].strip())
                        card2_int = Card.new(cards[1].strip())
                        return [card1_int, card2_int]
                except Exception as e:
                    if self.debug:
                        print(f"Error parsing hole cards from game state: {e}")
        
        # Fallback: reconstruct from hand class
        if not obs.pf_hand_class or obs.pf_hand_class == 'XX':
            return None
        
        try:
            # Parse hand class like "AKs", "72o", etc.
            hand_class = obs.pf_hand_class
            if len(hand_class) < 3:
                return None
            
            high_char = hand_class[0]
            low_char = hand_class[1]
            suit_char = hand_class[2] if len(hand_class) > 2 else 'o'
            
            # Convert to card strings
            if suit_char == 's':
                # Suited
                card1 = high_char + 's'
                card2 = low_char + 's'
            else:
                # Offsuit - use different suits
                card1 = high_char + 's'
                card2 = low_char + 'h'
            
            # Convert to integer representations
            card1_int = Card.new(card1)
            card2_int = Card.new(card2)
            
            return [card1_int, card2_int]
            
        except Exception as e:
            if self.debug:
                print(f"Error extracting hole cards: {e}")
            return None
    
    def _extract_board(self, obs: ObservationSchema, game_state: dict[str, Any] | None = None) -> list[int] | None:
        """
        Extract board cards from observation or game state.
        
        Args:
            obs: Game state observation
            game_state: Additional game state context
            
        Returns:
            List of board cards as integers, or None if not available
        """
        # Try to get board cards from game state first
        if game_state and 'community_cards' in game_state:
            board_cards_str = game_state['community_cards']
            if board_cards_str:
                try:
                    # Parse board cards string like "Ah,Kd,7c"
                    cards = board_cards_str.split(',')
                    board_ints = []
                    for card_str in cards:
                        card_str = card_str.strip()
                        if card_str:
                            board_ints.append(Card.new(card_str))
                    return board_ints
                except Exception as e:
                    if self.debug:
                        print(f"Error parsing board cards from game state: {e}")
        
        # Fallback: check street to determine board size
        street_index = np.argmax(obs.street_one_hot)
        
        if street_index == 0:  # Deal
            return []
        elif street_index == 1:  # Preflop
            return []
        else:
            # For flop/turn/river, we need the actual board cards
            # This is a fundamental limitation without game state
            if self.debug:
                print("Cannot extract board cards from observation - need game state")
            return None
    
    def reset(self) -> None:
        """Reset agent state between hands."""
        # Reset random state if using fixed seed
        if self.random_seed is not None:
            random.seed(self.random_seed)
            np.random.seed(self.random_seed)
