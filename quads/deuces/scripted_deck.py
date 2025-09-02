from typing import Iterable
from quads.deuces.deck import Deck
from quads.deuces.card import Card


class ScriptedDeck(Deck):
    """
    Deterministic deck that yields a pre-specified sequence of Deuces ints.
    Intended to fully replace shuffling. Any attempt to 'shuffle' is a no-op.
    """

    def __init__(self, card_text_sequence: Iterable[str]):
        # Normalize and convert to ints once using existing Card utilities
        self._cards = list(Card.hand_to_binary(list(card_text_sequence)))
        self.index = 0

    def shuffle(self):
        """No-op: deterministic deck order."""
        return

    def draw(self, n=1):
        """
        Return next n cards; raise if insufficient.
        
        Args:
            n: Number of cards to draw
            
        Returns:
            Single card int if n=1, list of card ints if n>1
            
        Raises:
            IndexError: If not enough cards remaining
        """
        if self.index + n > len(self._cards):
            raise IndexError(f"ScriptedDeck out of cards. Requested {n}, only {len(self._cards) - self.index} remaining.")
        
        out = self._cards[self.index:self.index + n]
        self.index += n
        return out[0] if n == 1 else out

    # Alias for compatibility if code expects deal() instead of draw()
    deal = draw