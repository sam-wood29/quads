import json
import sqlite3
from collections import deque
from typing import TYPE_CHECKING

import quads.engine.hand as hand_module

from .betting_order import BettingOrder
from .enums import ActionType, Phase
from .logger import get_logger

if TYPE_CHECKING:
    
    from .game_state import GameState
    from .hand import Hand

logger = get_logger(__name__)


class PhaseController:
    """Finite state machine for managing poker hand phases."""
    
    def __init__(self, state: "GameState", conn: sqlite3.Connection, hand: "Hand" = None):
        self.state = state
        self.conn = conn
        self.hand = hand  # Reference to Hand instance for pot awarding
        self.logger = get_logger(__name__)
    
    def __str__(self) -> str:
        """Comprehensive string representation for debugging."""
        # Current phase and street info
        current_phase = Phase(self.state.phase)
        street_number = self.state.street_number
        
        # Betting state
        highest_bet_dollars = self.state.highest_bet
        last_raise_dollars = self.state.last_raise_increment
        last_aggressor = self.state.last_aggressor_seat
        
        # Player states
        player_states = []
        for p in self.state.players:
            status_flags = []
            if p.has_folded:
                status_flags.append("FOLDED")
            if p.is_all_in:
                status_flags.append("ALL_IN")
            if self.state.acted_this_round.get(p.id, False):
                status_flags.append("ACTED")
            
            status_str = ",".join(status_flags) if status_flags else "ACTIVE"
            contrib_dollars = self.state.committed_this_round.get(p.id, 0.0)
            
            player_states.append(f"P{p.id}({p.position}, ${p.stack:.2f}, contrib=${contrib_dollars:.2f}, {status_str})")
        
        # Actionable seats
        actionable_str = f"Actionable: {list(self.state.actionable_seats)}" if self.state.actionable_seats else "Actionable: None"
        
        # Street settlement status
        is_settled = self._street_is_settled()
        is_uncontested = self._is_uncontested()
        all_matched = self._all_matched_and_rotated()
        all_all_in = self._all_remaining_all_in()
        
        return (f"PhaseController(phase={current_phase.value}, street={street_number}, "
                f"highest_bet=${highest_bet_dollars:.2f}, last_raise=${last_raise_dollars:.2f}, "
                f"last_aggressor=P{last_aggressor}, settled={is_settled}, "
                f"uncontested={is_uncontested}, all_matched={all_matched}, all_all_in={all_all_in})\n"
                f"    Players: [{', '.join(player_states)}]\n"
                f"    {actionable_str}\n"
                f"    Awarded uncontested: {self.state.awarded_uncontested}")
    
    def enter_phase(self, to_phase: Phase) -> None:
        """Transition to `to_phase`, log `phase_advance`, and run per-phase hooks."""
        # if i recall right, self.state.phase is gamestate type object.
        from_phase = Phase(self.state.phase)
        
        # if not changing phase, skip validation
        if to_phase == from_phase:
            self.logger.warning(f"Already in phase {to_phase}, skipping transition")
            return
        
        self._validate_transition(from_phase, to_phase)
        
        # Update state
        self.state.phase = to_phase.value
        self.state.street_number = self._street_number_for(to_phase)
        
        # Log phase advance
        self._log_phase_advance(to_phase, from_phase)
        
        # Per-phase hooks
        if to_phase in {Phase.PREFLOP, Phase.FLOP, Phase.TURN, Phase.RIVER}:
            self.start_betting_round()
    
    def start_betting_round(self) -> None:
        """Reset street-scoped variables and initialize betting order."""
        is_preflop = (Phase(self.state.phase) == Phase.PREFLOP)
        bb = self.state.big_blind
        
        # Reset street variables
        # TODO: look into what these street variables are...
        self.state.reset_street_vars(bb=bb, is_preflop=is_preflop)
        
        # Build actionable seats from BettingOrder
        num_players = len([p for p in self.state.players if not p.has_folded])
        current_phase = Phase(self.state.phase)
        
        try:
            order = BettingOrder.get_betting_order(num_players, current_phase)
            # Convert positions to player IDs
            actionable_ids = []
            for pos in order:
                player = next((p for p in self.state.players if p.position == pos.value), None)
                if player and self.state.is_seat_actionable(player.id):
                    actionable_ids.append(player.id)
            
            self.state.actionable_seats = deque(actionable_ids)
            # Very nice debugging statement here....
            self.logger.debug(f"Actionable seats for {current_phase}: {list(self.state.actionable_seats)}")
            
        except Exception as e:
            self.logger.error(f"Error building betting order: {e}")
            self.state.actionable_seats = deque()
    
    def maybe_close_street_and_advance(self) -> bool:
        """If betting is settled, advance to next phase or SHOWDOWN. Returns True if advanced."""
        if not self._street_is_settled():
            return False
        
        current_phase = Phase(self.state.phase)
        
        # Check for uncontested pot
        if self._is_uncontested():
            # Handle uncalled bets BEFORE awarding pot
            if self.hand and self.hand.last_aggressor:
                aggressor = self.hand._get_player_by_position(self.hand.last_aggressor)
                if aggressor:
                    self.hand._return_uncalled_bet(aggressor)
            
            self._award_uncontested_pot()
            self.enter_phase(Phase.SHOWDOWN)
            return True
        
        # Normal street progression
        if current_phase == Phase.RIVER:
            self.enter_phase(Phase.SHOWDOWN)
        else:
            next_phase = self._next_phase_after_street()
            self.enter_phase(next_phase)
        
        return True
    
    def _street_is_settled(self) -> bool:
        """Check if the current street is settled (betting complete)."""
        # Condition 1: Uncontested (only one active player)
        if self._is_uncontested():
            return True
        
        # Condition 2: All matched and full rotation completed
        if self._all_matched_and_rotated():
            return True
        
        # Condition 3: All remaining players are all-in
        if self._all_remaining_all_in():
            return True
        
        return False
    
    def _is_uncontested(self) -> bool:
        """Check if only one active player remains."""
        if not self.hand:
            # Fallback to GameState players if no hand reference
            active_players = [p for p in self.state.players if not p.has_folded]
            return len(active_players) == 1
        
        # Use actual Player objects from Hand for accurate fold status
        active_players = [p for p in self.hand.players if not p.has_folded]
        return len(active_players) == 1
    
    def _all_matched_and_rotated(self) -> bool:
        """Check if all players have matched the bet and a full rotation has occurred."""
        if self.state.highest_bet == 0:
            # No bet to match, check if everyone has acted
            return all(self.state.acted_this_round.values())
        
        # Check if all non-folded players have matched the bet
        for player in self.state.players:
            if not player.has_folded and not player.is_all_in:
                if self.state.committed_this_round.get(player.id, 0) < self.state.highest_bet:
                    return False
        
        # Check if a full rotation has occurred since last raise
        if self.state.last_aggressor_seat is None:
            # No raise yet, check if everyone has acted
            return all(self.state.acted_this_round.values())
        else:
            # There was a raise, check if everyone has acted since then
            return all(self.state.acted_this_round.values())
    
    def _all_remaining_all_in(self) -> bool:
        """Check if all remaining players are all-in."""
        if not self.hand:
            # Fallback to GameState players if no hand reference
            remaining_players = [p for p in self.state.players if not p.has_folded]
            if len(remaining_players) <= 1:
                return False
            return all(p.is_all_in for p in remaining_players)
        
        # Use actual Player objects from Hand for accurate status
        remaining_players = [p for p in self.hand.players if not p.has_folded]
        if len(remaining_players) <= 1:
            return False
        
        return all(p.all_in for p in remaining_players)
    
    def _award_uncontested_pot(self) -> None:
        """Award pot to the remaining active player."""
        print("DEBUG: _award_uncontested_pot called")
        
        if not self.hand:
            self.logger.error("No hand reference available for pot awarding")
            return
        
        # Prevent double awarding
        if self.state.awarded_uncontested:
            self.logger.info("Pot already awarded, skipping")
            return
        
        # Find the winner using actual Player objects from Hand
        winner = next((p for p in self.hand.players if not p.has_folded), None)
        if not winner:
            self.logger.error("No winner found for uncontested pot")
            return
        
        print(f"DEBUG: Winner found: player {winner.id}")
        print(f"DEBUG: Winner stack before: {winner.stack}")
        
        # Get pot amount from pot_manager (in cents)
        pot_cents = self.hand.pot_manager.total_table_cents()
        print(f"DEBUG: Pot amount: {pot_cents} cents (${pot_cents/100:.2f})")
        
        # Award the pot to the winner
        winner.stack += pot_cents
        
        print(f"DEBUG: Winner stack after: {winner.stack}")
        
        # Clear the pot manager after awarding
        self.hand.pot_manager.contributed = {pid: 0 for pid in self.hand.pot_manager.contributed}
        
        self.state.awarded_uncontested = True
        
        # Log the pot award
        self._log_pot_award(winner.id, pot_cents / 100.0)  # Convert to dollars for logging
        
        self.logger.info(f"Pot awarded to player {winner.id} (uncontested)")
    
    def _award_contested_pot(self) -> None:
        """Award pot based on showdown rankings."""
        print("DEBUG: _award_contested_pot called")
        
        if not self.hand:
            self.logger.error("No hand reference available for contested pot awarding")
            return
        
        # Prevent double awarding
        if self.state.awarded_uncontested:
            self.logger.info("Pot already awarded, skipping")
            return
        
        # Get player rankings from hand evaluation
        try:
            ranks = self.hand._rank_players_for_showdown()
            self.logger.info(f"Showdown rankings: {ranks}")
        except Exception as e:
            self.logger.error(f"Failed to rank players for showdown: {e}")
            return
        
        # Build pots from pot manager
        pots = self.hand.pot_manager.build_pots()
        self.logger.info(f"Built {len(pots)} pots for distribution")
        
        # Get seat order for stable tie-breaking
        seat_order = [p.id for p in sorted(self.hand.players, key=lambda p: p.seat_index)]
        
        # Use existing payout resolution logic
        from .payouts import resolve_payouts
        payouts = resolve_payouts(pots, ranks, seat_order)
        
        self.logger.info(f"Payouts calculated: {payouts}")
        
        # Apply payouts to player stacks
        for player_id, won_cents in payouts.items():
            if won_cents > 0:
                player = next((p for p in self.hand.players if p.id == player_id), None)
                if player:
                    player.stack += won_cents
                    self.logger.info(f"Player {player_id} won {won_cents} cents (${won_cents/100:.2f})")
                    
                    # Log the pot award
                    self._log_pot_award(player_id, won_cents / 100.0)
        
        # Clear the pot manager after awarding
        self.hand.pot_manager.contributed = {pid: 0 for pid in self.hand.pot_manager.contributed}
        
        self.state.awarded_uncontested = True
        self.logger.info("Contested pot awarded successfully")
    
    def _log_pot_award(self, winner_id: int, amount: float) -> None:
        """Log pot award action."""
        import quads.engine.hand as hand_module
        
        # Find the winner player object
        winner = next((p for p in self.state.players if p.id == winner_id), None)
        
        hand_module.log_action(
            conn=self.conn,
            game_session_id=self.state.game_session_id,
            hand_id=self.state.hand_id,
            step_number=self.state.next_step_number(),
            player=winner,  # Pass player object, not ID
            action=ActionType.WIN_POT.value,
            amount=amount,
            phase=self.state.phase,
            detail="Uncontested pot award"
        )
    
    def _log_phase_advance(self, to_phase: Phase, from_phase: Phase) -> None:
        """Log phase advance to database."""
        
        detail = {
            "from": from_phase.value,
            "to": to_phase.value,
            "street_number": self.state.street_number
        }
        
        hand_module.log_action(
            conn=self.conn,
            game_session_id=self.state.game_session_id,
            hand_id=self.state.hand_id,
            step_number=self.state.next_step_number(),
            player=None,  # No player for phase advances
            action=ActionType.PHASE_ADVANCE.value,
            amount=None,
            phase=to_phase.value,
            detail=json.dumps(detail)
        )
        
        self.logger.info(f"Phase advance: {from_phase.value} → {to_phase.value} (street {self.state.street_number})")
    
    def _next_phase_after_street(self) -> Phase:
        """Return the next phase given current phase."""
        current = Phase(self.state.phase)
        mapping = {
            Phase.PREFLOP: Phase.FLOP,
            Phase.FLOP: Phase.TURN,
            Phase.TURN: Phase.RIVER,
        }
        return mapping.get(current, Phase.SHOWDOWN)
    
    def _street_number_for(self, phase: Phase) -> int:
        """Map phase to street number."""
        # TODO: verify this, not sure if this is correct
        # looks like this is just assigning a numberic value to the phases of the hand.
        mapping = {
            Phase.DEAL: 0,
            Phase.PREFLOP: 1,
            Phase.FLOP: 2,
            Phase.TURN: 3,
            Phase.RIVER: 4,
            Phase.SHOWDOWN: 5,
        }
        return mapping.get(phase, 0)
    
    def _validate_transition(self, from_phase: Phase, to_phase: Phase) -> None:
        """Validate that the phase transition is legal."""
        # can showdown anytime after the deal
        allowed = {
            Phase.DEAL: {Phase.PREFLOP},
            Phase.PREFLOP: {Phase.FLOP, Phase.SHOWDOWN},
            Phase.FLOP: {Phase.TURN, Phase.SHOWDOWN},
            Phase.TURN: {Phase.RIVER, Phase.SHOWDOWN},
            Phase.RIVER: {Phase.SHOWDOWN},
        }
        
        if to_phase not in allowed.get(from_phase, set()):
            raise ValueError(f"Illegal phase transition: {from_phase.value} → {to_phase.value}")


# Helper function for external use
def street_is_settled(state: "GameState") -> bool:
    """Pure helper function to check if street is settled."""
    controller = PhaseController(state, None)  # No conn needed for this check
    return controller._street_is_settled() 