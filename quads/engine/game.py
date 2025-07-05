"""
game.py

Game class for managing a poker session (multiple hands).
This class handles player management and session-level operations.
"""
from typing import Optional, List
from quads.engine.logging_utils import setup_logger
from quads.engine.player import Player
from quads.engine.hand import Hand
from quads.engine.extras import Phase
import random

log = setup_logger(__name__)

class Game:
    """
    Main class for managing a poker session.
    Handles player management and orchestrates multiple hands.
    """
    def __init__(self,
                 small_blind: float = 0.25,
                 big_blind: float = 0.50,
                 players: Optional[List[Player]] = None
            ):
        """
        Initialize a new game session.
        """
        self.players: List[Player] = list()
        if players:
            self.add_players(players)
        self.small_blind = small_blind
        self.big_blind = big_blind
        self.dealer_index = 0
        self.hand_count = 0
        self.session_log = []
        
        log.debug(f"Game initialized with blinds: SB={small_blind}, BB={big_blind}")

    def add_players(self, players: List[Player]):
        """Add players to the game."""
        for player in players:
            self.add_player(player)

    def add_player(self, player: Player):
        """Add a single player to the game."""
        player.seat_index = len(self.players)
        self.players.append(player)
        log.debug(f"Added player: {player.name} at seat {player.seat_index}")

    def assign_seats(self, rng=None):
        """Randomly assign seat indices to players."""
        rng = rng or random
        rng.shuffle(self.players)
        for idx, player in enumerate(self.players):
            player.seat_index = idx
        log.debug(f"Seats assigned: {[(p.name, p.seat_index) for p in self.players]}")

    def rotate_dealer(self):
        """Rotate dealer to next active player."""
        n = len(self.players)
        for i in range(1, n + 1):
            next_index = (self.dealer_index + i) % n
            if self.players[next_index].is_playing:
                self.dealer_index = next_index
                log.debug(f"Dealer rotated to seat {self.dealer_index} ({self.players[next_index].name})")
                break

    def play_hand(self, hand_id: Optional[str] = None) -> dict:
        """
        Play a single hand.
        
        Returns:
            Dict containing hand results
        """
        if len([p for p in self.players if p.is_playing]) < 2:
            raise ValueError("Need at least 2 active players to play a hand")
        
        self.hand_count += 1
        hand_id = hand_id or f"hand_{self.hand_count:04d}"
        
        log.debug(f"Starting hand {hand_id}")
        
        # Create and play the hand
        hand = Hand(
            players=self.players,
            small_blind=self.small_blind,
            big_blind=self.big_blind,
            dealer_index=self.dealer_index,
            hand_id=hand_id
        )
        
        result = hand.play()
        
        # Log hand result
        self.session_log.append({
            "hand_id": hand_id,
            "result": result,
            "summary": hand.get_hand_summary()
        })
        
        # Rotate dealer for next hand
        self.rotate_dealer()
        
        log.debug(f"Hand {hand_id} completed. Winner: {[w.name for w in result['winners']]}")
        return result

    def play_session(self, num_hands: int) -> List[dict]:
        """
        Play multiple hands in a session.
        
        Args:
            num_hands: Number of hands to play
            
        Returns:
            List of hand results
        """
        log.debug(f"Starting session with {num_hands} hands")
        results = []
        
        for i in range(num_hands):
            try:
                result = self.play_hand()
                results.append(result)
            except Exception as e:
                log.error(f"Error in hand {i+1}: {e}")
                break
                
        log.debug(f"Session completed. Played {len(results)} hands")
        return results

    def get_session_summary(self) -> dict:
        """Get a summary of the entire session."""
        return {
            "total_hands": self.hand_count,
            "players": [p.name for p in self.players],
            "final_stacks": {p.name: p.stack for p in self.players},
            "session_log": self.session_log
        }
