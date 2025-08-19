from quads.engine.player import Player
import quads.engine.player as quads_player
from quads.engine.logger import get_logger
# from quads.engine.conn import get_conn
from quads.engine.game_state import GameState, PlayerState
from quads.engine.hand_parser import parse_hole_cards
from quads.deuces.deck import Deck
from quads.deuces.card import Card
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
                  conn: sqlite3.Connection, script: Optional[dict] = None, 
                  raise_settings: RaiseSetting = RaiseSetting.STANDARD, small_blind: float = 0.25, 
                  big_blind: float = 0.50, script_index: Optional[int] = None):
        self.players = players
        self.id = id
        self.deck = deck
        self.dealer_index = dealer_index
        self.game_session_id = game_session_id
        self.conn = conn
        self.script = script
        self.raise_settings = raise_settings
        self.deck = deck
        self.small_blind = small_blind
        self.big_blind = big_blind
        self.script_index = script_index
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
        # mostly building this in smoke_play.py to keep it managable right now.
        # This reset function could be grouped together -- what I am starting with here.
        self.phase = Phase.DEAL
        self.players = self._reset_players()
        self.dealer_index = self._advance_dealer()
        self.players_in_button_order = self._assign_positions()
        self._post_blinds()
        self._deal_hole_cards()
        
        
        
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
        conn = self.conn
        game_session_id = self.game_session_id
        hand_id = self.id
        step_number = self.step_number
        player = sb_player
        action = ActionType.POST_SMALL_BLIND
        amount = sb_paid
        phase = Phase.DEAL
        position = sb_player.position
        sb_logged = log_action(conn=conn, game_session_id=game_session_id,hand_id=hand_id,step_number=step_number,
                   player=player, action=action, amount=amount, phase=phase, position=position)
        self.step_number += 1
        player=bb_player
        action=ActionType.POST_BIG_BLIND
        amount=bb_paid
        position = bb_player.position
        bb_logged = log_action(conn=conn, game_session_id=game_session_id,hand_id=hand_id,step_number=step_number,
                   player=player, action=action, amount=amount, phase=phase, position=position)
        if not bb_logged or not sb_logged:
            raise RuntimeError("Error entering blinds posted into db.")
        
    def _get_next_script_action(self):
        if self.script_index >= len(self.script):
            raise RuntimeError("No more scripted actions")
        action = self.script[self.script_index]
        self.script_index += 1
        return action
        
    def _deal_hole_cards(self):
        players = self.players_in_button_order
        n = 1 % len(players)
        rotated_players = players[n:] + players[:n]
        for p in rotated_players:
            if self.script is not None: # scripted game
                script = self._get_next_script_action()
                if p.id != int(script['player']):
                    raise RuntimeError("Script / Game mismatch.")
                card_strings = script['cards']
                cards_for_db = ",".join(card_strings)
                cards_for_player = Card.hand_to_binary(card_strings)
            else:
                card1 = self.deck.draw()
                card2 = self.deck.draw()
                cards_for_player = [card1, card2]
                card_strings = [Card.int_to_str(card1), Card.int_to_str(card2)]
                cards_for_db = ",".join(card_strings)
            p.hole_cards = cards_for_player
            features = parse_hole_cards(cards_for_db)
            success = log_action(conn=self.conn, game_session_id=self.game_session_id, hand_id=self.id,
                                 step_number=self.step_number, player=p, action=ActionType.DEAL_HOLE,
                                 phase=Phase.DEAL, hole_cards=cards_for_db,
                                 hole_card1=features.get("hole_card1"), hole_card2=features.get("hole_card2"), pf_hand_class=features.get("hand_class"),
                                 high_rank=features.get("high_rank"), low_rank=features.get("low_rank"), is_pair=features.get("is_pair"),
                                 is_suited=features.get("is_suited"), gap=features.get("gap"), chen_score=features.get("chen_score"))
            self.step_number += 1
            if not success:
                raise RuntimeError(f"Unable to log action while dealing hole cards.")
            
    def _get_betting_round_action_order(self):
        players = self.players_in_button_order
        num_players = len(players)
        if num_players == 2:
            if self.phase == Phase.PREFLOP:
                players_in_order = [players[0], players[1]]
            else:
                players_in_order = [players[1], players[0]]
        else:
            if self.phase == Phase.PREFLOP:
                last_player = next(p for p in players if p.position == quads_player.Position.BB)
            else:
                last_player = next(p for p in players if p.position == quads_player.Position.BUTTON)
            idx = players.index(last_player)
            next_idx = (idx + 1) % num_players
            players_in_order = players[next_idx:] + players[:next_idx]
        return players_in_order
    
    
    def _rebuild_players_yet_to_act_after_raise(self, action_order: list[Player], raiser: Player) -> list[Player]:
        highest_bet = self.highest_bet
        remaining = [
            p for p in action_order
            if (not p.has_folded) and (p.stack > 0) and (p is not raiser) and (p.current_bet < highest_bet)
        ]
        raiser_index = action_order.index(raiser)
        ordered = []
        for i in range(len(action_order) - 1):
            idx = (raiser_index + 1 + i) % len(action_order)
            candidate = action_order[idx]
            if candidate in remaining:
                ordered.append(candidate)
        return ordered
    
    def _generate_raise_amounts(self, player: Player, min_raise, max_raise):
        amounts = []
        current = min_raise
        step = self.small_blind
        while current <= max_raise and current <= player.stack:
            amounts.append(current)
            current += step
        return amounts
    
    def _get_valid_actions(self, player:Player, amount_to_call:float):
        if self.raise_settings != RaiseSetting.STANDARD:
            raise RuntimeError("Raise settings not implemented.")
        va = {
            'actions': [],
            'raise_amounts': [],
        }
        va["actions"].append(ActionType.FOLD)
        if amount_to_call > 0:
            va["actions"].append(ActionType.CALL)
        else:
            va["actions"].append(ActionType.CHECK)
        if player.stack > amount_to_call:
            if self.last_raise_increment == 0:
                min_raise_amount = self.big_blind
                min_raise = self.highest_bet + min_raise_amount
            else:
                min_raise = self.highest_bet + self.last_raise_increment
            max_raise = player.stack
            if min_raise <= max_raise:
                va["actions"].append(ActionType.RAISE)
        va["raise_amounts"] = self._generate_raise_amounts(player=player, min_raise=min_raise, max_raise=max_raise)
        return va, amount_to_call
            
        
    def _select_validate_action(self, ap: Player, valid_actions: dict):
        if self.script is not None:
            action = self._get_next_script_action()
            if action["type"] == "action":
                if not ap.id == action["player"]:
                    raise ValueError ("Script mismatch.")
                r_action = action["move"]
                r_amount = action["amount"]
            if action["type"] == 'test':
                raise RuntimeError("test scipt 'Actions' not yet implemented.")
        else:
            raise RuntimeError("Unscripted play not implemented yet.")
            # r_actions
            # r_amount
        match r_action:
            case "check":
                r_action = ActionType.CHECK
            case "fold":
                r_action = ActionType.FOLD
            case "call":
                r_action = ActionType.CALL
            case "raise":
                r_action = ActionType.RAISE
                if r_amount not in valid_actions["raise_amounts"]:
                    if self.script is not None:
                        raise ValueError("Invalid raise amount in script.")
                    else:
                        raise RuntimeError("Unscripted play not supported yet.")
        if r_action not in valid_actions["actions"]:
            if self.script is not None:
                raise ValueError("Invalid action in script")
            else:
                raise ValueError("Unscripted play not supported yet.")
        return r_action, r_amount
    
    def _get_player_action(self, acting_player: Player, game_state: GameState):
        ap = acting_player
        amount_to_call = self.highest_bet - ap.current_bet
        valid_actions, amount_to_call = self._get_valid_actions(player=ap, amount_to_call=amount_to_call)
        selected_action, selected_amount = self._select_validate_action(ap=ap,valid_actions=valid_actions)
        return selected_action, selected_amount, amount_to_call
    
    def handle_player_action(self, game_state: GameState, selected_action: ActionType, selected_amount: float,
                             acting_player: Player, amount_to_call: float, highest_bet: float):
        player = acting_player
        pot_before = self.pot
        player_stack_before=acting_player.stack
        if selected_action==ActionType.FOLD:
            player.has_folded = True
            total_bet = None
        elif selected_action == ActionType.CALL:
            if amount_to_call > player.stack:
                print("Need to create a side pot here.")
            call_amount = min(amount_to_call, player.stack)
            player.stack -= call_amount
            player.current_bet += call_amount
            player.round_contrib += call_amount
            self.pot += call_amount
            total_bet = None
        elif selected_action == ActionType.RAISE:
            total_bet = selected_amount
            additional_bet = total_bet - player.current_bet
            prev_highest_bet = self.highest_bet
            player.stack -= additional_bet
            player.current_bet += additional_bet
            player.round_contrib += additional_bet
            self.pot += additional_bet
            self.highest_bet = player.current_bet
            # Update last_raise_increment only if this is a full raise (not an all-in for less)
            raise_incr = self.highest_bet - prev_highest_bet
            if prev_highest_bet == 0 or raise_incr >= getattr(self, "last_raise_increment", 0):
                self.last_raise_increment = raise_incr
        return selected_action


    def _run_betting_round(self):
        if self.phase == Phase.PREFLOP:
            self.last_raise_increment = self.big_blind
        action_order = self._get_betting_round_action_order()
        self.highest_bet = max(p.current_bet for p in action_order)
        players_yet_to_act = [p for p in action_order if not p.has_folded and p.stack > 0]
        while players_yet_to_act:
            acting_player = players_yet_to_act.pop(0)
            game_state = self.get_game_state(action_on_player_id=acting_player.id)
            selected_action, selected_amount, amount_to_call = self._get_player_action(acting_player=acting_player, game_state=game_state)
            result = self.handle_player_action(game_state=game_state, selected_action=selected_action, selected_amount=selected_amount,
                                               acting_player=acting_player, amount_to_call=amount_to_call, highest_bet=self.highest_bet)
            # If the acting player raises (or bets from 0), everyone else who hasn't matched must act again.
            if result == ActionType.RAISE:
                players_yet_to_act = self._rebuild_players_yet_to_act_after_raise(action_order=action_order, raiser=acting_player)
            # If no one left to act, the betting round ends.
            if not players_yet_to_act:
                break

    def get_game_state(self, action_on_player_id: int = None, last_action: dict = None) -> GameState:
        player_states = []
        for p in self.players:
            # Convert integer hole cards to string if needed
            if p.hole_cards and isinstance(p.hole_cards, list):
                from quads.deuces.card import Card
                hole_cards = [Card.int_to_str(c) if isinstance(c, int) else c for c in p.hole_cards]
            else:
                hole_cards = None
            player_states.append(PlayerState(
                id=p.id,
                name=p.name,
                stack=p.stack,
                position=str(p.position) if p.position else None,
                hole_cards=hole_cards,
                has_folded=p.has_folded,
                is_all_in=p.all_in,
                current_bet=p.current_bet,
                round_contrib=p.round_contrib,
                hand_contrib=p.hand_contrib
            ))
        # Add community card attribute to Hand Class
        community_cards = getattr(self, 'community_cards', [])
        if community_cards and isinstance(community_cards[0], int):
            from quads.deuces.card import Card
            community_cards = [Card.int_to_str(c) for c in community_cards]
        return GameState(
            hand_id=self.id,
            phase=str(self.phase),
            pot=self.pot,
            community_cards=community_cards,
            players=player_states,
            action_on=action_on_player_id,
            last_action=last_action,
            min_raise=getattr(self, 'min_raise', 0.0),
            max_raise=getattr(self, 'max_raise', 0.0),
            small_blind=self.small_blind,
            big_blind=self.big_blind,
            dealer_position=str(self.players[self.dealer_index].position) if self.dealer_index is not None else ''
        )
            
    
def log_action(
    conn: sqlite3.Connection,
    game_session_id: int,
    hand_id: int,
    step_number: int,
    player: Player,
    action: str,
    amount: float = None,
    phase: str = None,
    cards: str = None,
    hole_cards: str = None,
    community_cards: str = None,
    hand_rank: int = None,
    hand_class: str = None,
    pot_odds: float = None,
    percent_stack_to_call: float = None,
    amount_to_call: float = None,
    highest_bet: float = None,
    position: str = None,
    detail: str = None,
    hole_card1: str = None,
    hole_card2: str = None,
    pf_hand_class: str = None,
    high_rank: int = None,
    low_rank: int = None,
    is_pair: int = None,
    is_suited: int = None,
    gap: int = None,
    chen_score: float = None
) -> bool:
    try:
        cursor = conn
        cursor.execute("""
            INSERT INTO actions (
                game_session_id, hand_id, step_number, player_id, action, amount,
                phase, cards, hole_cards, community_cards,
                hand_rank, hand_class, pot_odds, percent_stack_to_call,
                amount_to_call, highest_bet, position, detail,
                hole_card1, hole_card2, pf_hand_class, high_rank, low_rank, is_pair, is_suited, gap, chen_score
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            game_session_id, hand_id, step_number, player.id, action, amount,
            phase, cards, hole_cards, community_cards,
            hand_rank, hand_class, pot_odds, percent_stack_to_call,
            amount_to_call, highest_bet, position, detail,
            hole_card1, hole_card2, pf_hand_class, high_rank, low_rank, is_pair, is_suited, gap, chen_score
        ))
        conn.commit()
        return True
    except Exception as e:
        print(f"ERROR - Failed to log action: {e}")
        return False
