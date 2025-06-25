from quads.engine.logging_utils import setup_logger
from quads.deuces import Card, Deck
from quads.deuces.lookup import LookupTable

logger = setup_logger(name=__name__,
                      log_file='logs/t.log')
logger.info('yahoo a logger was setup in record timing this time.')

def test_logger():
    """
    There is a more effecient way to read a line in the file, 
    that i am not going to worry about.
    """
    with open(
        file="logs/t.log",
        mode='r',
    ) as f:
        lines = f.readlines()
        raw_line = lines[0].strip() if lines else None
        raw_line = repr(raw_line)
        my_slice = raw_line[-6:-1]
        assert my_slice == 'time.'

class TestCard:
    def test_card_one(self):
        """
        Ensure that card encoding logic produces the expected 32-bit value:
        """
        card = Card.new('Td')
        # Verify str -> int encoding:
        assert card == 16_795_671
        # Verify fits within 32 bit integer:
        assert card < 2**32
        assert card.bit_length() <= 32
        # Verify bit_count (How many ones in the binary):
        bit_count = bin(card).count('1')
        expected_bit_count = 7
        assert bit_count == expected_bit_count
        # Verify fields are encoded correctly:
        assert Card.get_rank_int(card) == 8
        assert Card.get_suit_int(card) == 4
        assert Card.get_prime(card) == 23
        assert Card.get_bitrank_int(card) == (1 << 8)
        # Str repr:
        assert Card.int_to_str(card) == 'Td'
        # pretty str:
        output = Card.int_to_pretty_str(card)
        assert isinstance(output, str)

        logger.info(f'bitcount: {bit_count}\n'
                    f'card bit lenght: {card.bit_length()}\n'
                    f'rank_int: {Card.get_rank_int(card)}\n'
                    f'suit_int: {Card.get_suit_int(card)}\n'
                    f'prime: {Card.get_prime(card)}\n'
                    f'bitrank: {Card.get_bitrank_int(card)}\n'
                    f'str: {Card.int_to_str(card)}\n'
                    f'pretty str: {output}\n')

    def test_card_two(self):
        """
        Not really important:
        """
        hand = [Card.new('3d'), Card.new('2h')]
        assert len(hand) == 2
        assert all(isinstance(card, int) for card in hand)

        sorted_hand = sorted(hand)
        assert set(hand) == set(sorted_hand)
        pretty_str_hand = [Card.int_to_pretty_str(card) for card in hand]
        logger.info(f'pretty hand: {Card.print_pretty_cards(hand)}\n'
                    f'pretty sorted hand: {Card.print_pretty_cards(sorted_hand)}\n'
                    'Another fun...\n'
                    f'pretty_str: {pretty_str_hand}')
        

class TestDeck:
    def test_deck_one(self):
        deck = Deck()
        sorted_cards = sorted(deck.cards)
        readable_cards = [Card.int_to_str(card) for card in sorted_cards]
        logger.info(f'readable cards: \n\n{readable_cards}')
        assert len(set(deck.cards)) == 52
        deck2 = Deck()
        # decks are same, deck.cards aren't
        assert deck.cards != deck2.cards
        hand = deck.draw(2)
        logger.info(f'hand: {[Card.int_to_str(c) for c in hand]}')
        for card in hand:
            # .draw returns encoded card (int)
            assert isinstance(card, int)

class TestLookup:
    def test_lookup_one(self):
        def test_lookup_table_size():
            table = LookupTable()
            assert hasattr(table, "flush_lookup")
            assert isinstance(table.flush_lookup, dict)
            assert isinstance(table.flush_lookup, dict)
            assert isinstance(table.unsuited_lookup, dict)

            flush_count = len(table.flush_lookup)
            assert flush_count == 1287, f'Expected 1287 flush entries, got {flush_count}'

            straight_count = 10
            actual_straights = [
                p for p, r in table.unsuited_lookup.items()
                if r >= LookupTable.MAX_FLUSH + 1 and r <= LookupTable.MAX_STRAIGHT
            ]
            assert len(actual_straights) == straight_count, f'Expected 10 straights, got {len(actual_straights)}'

            high_card_count = 1277
            actual_high_cards = [
                p for p, r in table.unsuited_lookup.items()
                if r >= LookupTable.MAX_PAIR + 1
            ]
            assert len(actual_high_cards) == high_card_count, f'Expected 1277 high cards, got {len(actual_high_cards)}'

            # Royal fluch bit pattern: 0b1111100000000 = 7936
            prime_product = Card.prime_product_from_rankbits(7936)
            assert table.flush_lookup[prime_product] == 1

            # All values in the flush/unsuited tables should be unique and within [1, 7462]
            all_ranks = list(list(table.flush_lookup.values()) + list(table.unsuited_lookup.values()))
            assert len(all_ranks) == len(set(all_ranks)) # no duplicates
            assert all(1 <= r <= 7462 for r in all_ranks)
            
        test_lookup_table_size()