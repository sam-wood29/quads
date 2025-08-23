import json
import os
import sqlite3
from datetime import UTC, datetime
from enum import Enum

import quads.engine.player as quads_player
from quads.deuces.deck import Deck
from quads.engine.conn import get_conn
from quads.engine.hand import Hand
from quads.engine.logger import get_logger
from quads.engine.player import Player


class ReBuySetting(Enum):
    ONE_LEFT = "one_left"

class GameType(Enum):
    MANUAL = "manual"
    SCRIPTED = "scripted"

class GameSession:
    def __init__(self, players: list[Player], gametype: GameType, data: dict | None, script: dict | None, rebuy_setting: ReBuySetting, small_blind: float = 0.25, big_blind: float = 0.50):
        self.players = players
        self.gametype = gametype
        self.script = script
        self.rebuy_setting = rebuy_setting
        self.small_blind = small_blind
        self.big_blind = big_blind
        self.deck = Deck()
        self.dealer_index = -1
        self.logger = get_logger(__name__)
        if gametype == GameType.SCRIPTED and script is None:
            raise ValueError("A Script must be provided for this game type.")
        self.conn = get_conn()
        self.session_id = self._create_game_session_in_db(data)
        if self.script is not None:
            self.script_index = 0


    def __str__(self) -> str:
        return f"{[p.__str__() for p in self.players]}\n{self.gametype}"
    
    def __del__(self):
        if hasattr(self, 'conn'):
            self.conn.close()
    
    def play(self):
        hand_id = 1
        keep_playing = True
        players = self.players
        deck = self.deck
        script = self.script
        while keep_playing:
            hand = Hand(players=players, id=hand_id, deck=deck, script=script, 
                        dealer_index=self.dealer_index, game_session_id=self.session_id,
                        conn=self.conn)
            players, hand_id, deck, keep_playing, script, dealer_index = hand.play()
        self.conn.close()
            
            
    def _create_game_session_in_db(self, data: dict, conn: sqlite3.Connection = get_conn()):
        cursor = conn.cursor()
        script_name = data.get("script_name")
        same_stack = data.get("same_stack")
        stack_amount = data.get("stack_amount")
        if same_stack is None or stack_amount is None:
            raise RuntimeError("Script stack amount and/or settings not specified.")
        cursor.execute(
            """
            INSERT INTO game_sessions (
                created_at,
                object_game_type,
                small_blind,
                big_blind,
                same_stack,
                rebuy_setting,
                stack_amount,
                script_name
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S"),
                self.gametype.value,
                self.small_blind,
                self.big_blind,
                same_stack,
                self.rebuy_setting.value,
                stack_amount,
                script_name
            ),
        )
        conn.commit()
        session_id = cursor.lastrowid
        conn.close()
        return session_id
        
        
def run_scripted_game_session(script: str):
    """
    1. load players from script - CHECK
    2. initalize players from script - CHECK
    3. initalize game with script
    4. Play the game with the script.    
    """
    game = create_game_from_script(script=script)
    print(game) # this is a filler for ruff - Not sure what is going on here.
    

def create_game_from_script(script: str):
    script_path = find_script_path(script=script)
    with open(script_path) as f:
        data = json.load(f)
    player_data = data["players"]
    same_stack = data["same_stack"]
    stack_amount = data["stack_amount"]    
    game_players = quads_player.create_load_player_from_script(player_data=player_data, same_stack=same_stack, stack_amount=stack_amount)
    script = data['script']
    small_blind = data['small_blind']
    big_blind = data['big_blind']
    rebuy_setting = data['rebuy_setting']
    if rebuy_setting == "one_left":
        rebuy_setting = ReBuySetting.ONE_LEFT
    else:
        raise RuntimeError(f"Rebuy setting: {rebuy_setting} not implemented.")
    game_session = GameSession(players=game_players, gametype=GameType.SCRIPTED, data=data, rebuy_setting=rebuy_setting, script=script, small_blind=small_blind, big_blind=big_blind)
    print(game_session.__str__())
    return game_session
    
        
def find_script_path(script: str):
    great_grand_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    target_dir = os.path.join(great_grand_dir, 'tests/test_data')
    target_file = os.path.join(target_dir, script)
    return target_file
    