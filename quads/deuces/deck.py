import time
from random import seed, shuffle

from .card import Card


class Deck:
    """
    Class representing a deck. The first time we create, we seed the static 
    deck with the list of unique card integers. Each object instantiated simply
    makes a copy of this object and shuffles it. 
    """
    _FULL_DECK = []
    _seed_set = False

    def __init__(self):
        self.shuffle()

    def shuffle(self):
        self.cards = Deck.GetFullDeck()
        shuffle(self.cards)
        
    @classmethod
    def set_seed(cls, seed_value: int):
        """Set a random seed for reproducible shuffling."""
        seed(seed_value)
        cls._seed_set = True
    
    @classmethod
    def reset_seed(cls):
        """Reset to random seed"""
        seed(int(time.time() * 1000000))
        cls._seed_set = False

    def draw(self, n=1):
        if n == 1:
            return self.cards.pop(0)

        cards = []
        for i in range(n):
            cards.append(self.draw())
        return cards

    def __str__(self):
        return Card.print_pretty_cards(self.cards)

    @staticmethod
    def GetFullDeck():
        if Deck._FULL_DECK:
            return list(Deck._FULL_DECK)

        # create the standard 52 card deck
        for rank in Card.STR_RANKS:
            for suit,val in Card.CHAR_SUIT_TO_INT_SUIT.items():
                Deck._FULL_DECK.append(Card.new(rank + suit))

        return list(Deck._FULL_DECK)