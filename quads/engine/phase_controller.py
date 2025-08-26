import json
import sqlite3
from collections import deque
from typing import TYPE_CHECKING

from .betting_order import BettingOrder
from .enums import ActionType, Phase
from .logger import get_logger

if TYPE_CHECKING:
    from .game_state import GameState

logger = get_logger(__name__)


class PhaseController:
    """Finite state machine for managing poker hand phases."""
    
    def __init__(self, state: "GameState", conn: sqlite3.Connection):
        self.state = state
        self.conn = conn
        self.logger = get_logger(__name__)
    
    def enter_phase(self, to_phase: Phase) -> None:
        """Transition to `to_phase`, log `phase_advance`, and run per-phase hooks."""
        from_phase = Phase(self.state.phase)
        
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
        active_players = [p for p in self.state.players if not p.has_folded]
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
        remaining_players = [p for p in self.state.players if not p.has_folded]
        if len(remaining_players) <= 1:
            return False
        
        return all(p.is_all_in for p in remaining_players)
    
    def _award_uncontested_pot(self) -> None:
        """Award pot to the remaining active player."""
        winner = next((p for p in self.state.players if not p.has_folded), None)
        if not winner:
            self.logger.error("No winner found for uncontested pot")
            return
        
        self.state.awarded_uncontested = True
        
        # Log the pot award
        self._log_pot_award(winner.id, self.state.pot)
        
        self.logger.info(f"Pot awarded to player {winner.id} (uncontested)")
    
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
        import quads.engine.hand as hand_module
        
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