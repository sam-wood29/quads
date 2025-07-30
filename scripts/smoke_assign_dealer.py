import quads.engine.game as quads_game
import quads.engine.hand as quads_hand

def main():
    game = quads_game.create_game_from_script('test_script1.json')
    hand = quads_hand.Hand(players=game.players,id=1,deck=game.deck,dealer_index=game.dealer_index,
                           script=game.script, game_session_id=game.session_id)
    hand.players = hand._reset_players()
    hand.dealer_index = hand._advance_dealer()
    print(f"hand.dealer_index {hand.dealer_index}")
    hand.phase = quads_hand.Phase.DEAL
    hand.players_in_button_order = hand._assign_positions()
    hand._post_blinds()
    for p in hand.players:
        print(p.__str__())
    

if __name__ == "__main__":
    main()