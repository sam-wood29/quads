from quads.engine.player import Player
import quads.engine.player as quads_player
from quads.engine.logger import get_logger
from quads.engine.conn import get_conn
from quads.deuces.deck import Deck
from enum import Enum
from typing import Optional
from collections import deque
import sqlite3

class RaiseSetting(Enum):
    STANDARD = "standard"
    
class Phase(str, Enum):
    DEAL = "deal"
    PREFLOP = "preflop"
    TURN = "turn"
    RIVER = "river"
    SHOWDOWN = "showdown"
    
class ActionType(str, Enum):
    CALL = "call"
    RAISE = "raise"
    CHECK = "check"
    FOLD = "fold"
    BET = "bet"
    DEAL_HOLE = "deal_hole"
    DEAL_COMMUNITY = "deal_community"
    WIN_POT = "win_pot"
    POST_SMALL_BLIND = "post_small_blind"
    POST_BIG_BLIND = "post_big_blind"

class Hand:
    def __init__ (self, players: list[Player], id: int, deck: Deck, dealer_index: int, game_session_id: int, 
                  script: Optional[dict] = None, raise_settings: RaiseSetting = RaiseSetting.STANDARD, 
                  small_blind: float = 0.25, big_blind: float = 0.50):
        self.players = players
        self.id = id
        self.deck = deck
        self.dealer_index = dealer_index
        self.game_session_id = game_session_id
        self.script = script
        self.raise_settings = raise_settings
        self.deck = deck
        self.small_blind = small_blind
        self.big_blind = big_blind
        self.pot = 0.0
        self.step_number = 1
        self.phase: Phase
        self.logger = get_logger(__name__)
    
    def play(self):
        if self.script is not None:
            self.play_scripted()
        else:
            self.play_manual()
        # Eventually
        # return players, hand_id, keep_playing, script, dealer_index
    
    def play_scripted(self):
        # This reset function could be grouped together -- what I am starting with here.
        self.phase = Phase.DEAL
        self.players = self._reset_players()
        self.dealer_index = self._advance_dealer()
        self.players_in_button_order = self._assign_positions()
        self._post_blinds() # if want to return something here in future, put in in the action db table.
        
        
    def play_manual(self):
        raise RuntimeError("Manual Play not implemented yet.")
        
    def _reset_players(self):
        for p in self.players:
            p.has_folded = False
            p.round_contrib = 0.0
            p.hand_contrib = 0.0
            p.hole_cards = None
            p.has_acted = False
            p.all_in = False
            p.position = None
        return self.players
    
    def _advance_dealer(self):
        players = sorted(
            [p for p in self.players],
            key=lambda p: p.seat_index
        )
        current_seat = self.dealer_index
        seat_indices = [p.seat_index for p in players]
        try:
            current_idx = seat_indices.index(current_seat)
        except ValueError:
            current_idx = -1
        next_idx = (current_idx + 1) % len(seat_indices)
        dealer_index = seat_indices[next_idx]
        return dealer_index
    
    def _assign_positions(self):
        players=sorted(
            [p for p in self.players],
            key=lambda p: p.seat_index
        )
        num_players = len(players)
        if 2 > num_players or num_players > 10:
            raise ValueError(f"{num_players} players not supported.")
        position_names = quads_player.POSITIONS_BY_PLAYER_COUNT[num_players]
        seat_indices = [p.seat_index for p in players]
        dealer_seat = self.dealer_index
        try:
            dealer_pos_in_list = seat_indices.index(dealer_seat)
        except ValueError:
            raise ValueError("Dealer index not found amoung active players")
        rotated_players = deque(players)
        rotated_players.rotate(-dealer_pos_in_list)
        players_in_order = []
        for pos, player in zip(position_names, rotated_players):
            player.position = pos
            players_in_order.append(player)
        return players_in_order
    
    def _post_blinds(self):
        sb_amount = self.small_blind
        bb_amount = self.big_blind
        ordered_player_list = self.players_in_button_order
        if len(ordered_player_list) == 2:
            bb_player = ordered_player_list[1]
            sb_player = ordered_player_list[0]
        else:
            sb_player = ordered_player_list[1]
            bb_player = ordered_player_list[2]
        sb_paid = min(sb_amount, sb_player.stack)
        bb_paid = min(bb_amount, bb_player.stack)
        sb_player.stack -= sb_paid
        sb_player.hand_contrib += sb_paid
        sb_player.round_contrib += sb_paid
        sb_player.current_bet += sb_paid
        bb_player.stack -= bb_paid
        bb_player.hand_contrib += bb_paid
        bb_player.round_contrib += bb_paid
        bb_player.current_bet += bb_paid
        self.pot += (bb_paid + sb_paid)
        sb_action_logged = _log_action_in_db(conn=get_conn(), hand=self, player=sb_player, action=ActionType.POST_SMALL_BLIND, 
                                             amount=sb_paid, phase=self.phase, cards=None, detail=None)
        bb_action_logged = _log_action_in_db(conn=get_conn(), hand=self, player=bb_player, action=ActionType.POST_BIG_BLIND, 
                                             amount=bb_paid, phase=self.phase, cards=None, detail=None)
        # In future going to pass conn throughout the entire hand.
        
        
        
    def _deal_hole_cards(self):
        if self.script is not None:
            print(f"dealing hole cards from script.")
        else:
            raise RuntimeError(f"Random deal not implemented yet.")
    
def _log_action_in_db(
    conn: sqlite3.Connection,
    hand: Hand,
    player: Player,
    action: str,
    amount: float = None,
    phase: str = None,
    cards: str = None,
    detail: str = None
) -> bool:
    try:
        cursor = conn.cursor()
        cursor.execute("""
                       INSERT INTO actions (game_session_id, hand_id, step_number, player_id, action, amount, phase, cards, detail, position)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        hand.game_session_id,
                        hand.id, 
                        hand.step_number, 
                        player.id, 
                        action, 
                        amount, 
                        hand.phase, 
                        cards, 
                        detail,
                        str(player.position)
                    ))
        conn.commit()
        hand.step_number += 1
        conn.close()
        return True
    except Exception as e:
        print(f"ERROR - failed to log action; error: {e}")
        return False