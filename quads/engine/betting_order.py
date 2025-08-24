
from .enums import Phase
from .player import Position


class BettingOrder:
    """
    Defines betting order for all poker scenarios.

    The betting order is determined by:
    1. Number of players at the table
    2. Current phase of the hand
    3. Position assignments relative to the button
    """

    # Preflop betting order (first to act is left of BB; heads-up: SB then BB)
    PREFLOP_ORDER: dict[int, list[Position]] = {
        2: [Position.SB, Position.BB],
        3: [Position.BUTTON, Position.SB, Position.BB],  # fixed: no UTG at 3-handed
        4: [Position.UTG, Position.BUTTON, Position.SB, Position.BB],
        5: [Position.UTG, Position.CO, Position.BUTTON, Position.SB, Position.BB],
        6: [Position.UTG, Position.HJ, Position.CO, Position.BUTTON, Position.SB, Position.BB],
        7: [Position.UTG, Position.MP, Position.HJ, Position.CO, Position.BUTTON, Position.SB, Position.BB],
        8: [Position.UTG, Position.UTG1, Position.MP, Position.HJ, Position.CO, Position.BUTTON, Position.SB, Position.BB],
        9: [Position.UTG, Position.UTG1, Position.UTG2, Position.MP, Position.HJ, Position.CO, Position.BUTTON, Position.SB, Position.BB],
        10: [Position.UTG, Position.UTG1, Position.UTG2, Position.MP, Position.LJ, Position.HJ, Position.CO, Position.BUTTON, Position.SB, Position.BB],
    }

    # Postflop betting order (first to act is left of the button; button last)
    POSTFLOP_ORDER: dict[int, list[Position]] = {
        2:  [Position.BB, Position.SB],  # heads-up special case: BB first, SB(button) last
        3:  [Position.SB, Position.BB, Position.BUTTON],
        4:  [Position.SB, Position.BB, Position.UTG, Position.BUTTON],
        5:  [Position.SB, Position.BB, Position.UTG, Position.CO, Position.BUTTON],
        6:  [Position.SB, Position.BB, Position.UTG, Position.HJ, Position.CO, Position.BUTTON],
        7:  [Position.SB, Position.BB, Position.UTG, Position.MP, Position.HJ, Position.CO, Position.BUTTON],
        8:  [Position.SB, Position.BB, Position.UTG, Position.UTG1, Position.MP, Position.HJ, Position.CO, Position.BUTTON],
        9:  [Position.SB, Position.BB, Position.UTG, Position.UTG1, Position.UTG2, Position.MP, Position.HJ, Position.CO, Position.BUTTON],
        10: [Position.SB, Position.BB, Position.UTG, Position.UTG1, Position.UTG2, Position.MP, Position.LJ, Position.HJ, Position.CO, Position.BUTTON],
    }

    @classmethod
    def get_betting_order(
        cls,
        num_players: int,
        phase: Phase,
        button_pos: Position = None,  # Keep for API compatibility, but not used
    ) -> list[Position]:
        """
        Get the betting order for a specific player count and phase.

        Args:
            num_players: Number of players at the table (2-10)
            phase: Current phase of the hand (PREFLOP, FLOP, TURN, RIVER)
            button_pos: Kept for API compatibility (not used in position-relative approach)

        Returns:
            List of positions in betting order (first to act -> last to act)

        Raises:
            ValueError: If player count is not supported
        """
        if num_players not in cls.PREFLOP_ORDER:
            raise ValueError(f"Unsupported player count: {num_players}. Must be 2-10.")

        if phase == Phase.PREFLOP:
            return cls.PREFLOP_ORDER[num_players]
        else:
            # FLOP, TURN, RIVER all use the same postflop order
            return cls.POSTFLOP_ORDER[num_players]

    @classmethod
    def get_first_to_act(cls, player_count: int, phase: Phase) -> Position:
        """Get the first position to act in the current phase."""
        order = cls.get_betting_order(player_count, phase)
        return order[0]

    @classmethod
    def get_last_to_act(cls, player_count: int, phase: Phase) -> Position:
        """Get the last position to act in the current phase."""
        order = cls.get_betting_order(player_count, phase)
        return order[-1]

    @classmethod
    def get_next_position(
        cls,
        player_count: int,
        phase: Phase,
        current_position: Position,
        *,
        wrap: bool = True,
    ) -> Position | None:
        """
        Get the next position to act after the current position.

        Args:
            player_count: Number of players at the table
            phase: Current phase of the hand
            current_position: Current position that just acted
            wrap: If True (default), wraps around from last -> first. If False, returns
                  None when current_position is the last to act.

        Returns:
            Next position to act, or None if `wrap=False` and current is last; None
            also if `current_position` is not found in the order.
        """
        order = cls.get_betting_order(player_count, phase)
        try:
            idx = order.index(current_position)
        except ValueError:
            return None

        if idx == len(order) - 1:
            return order[0] if wrap else None
        return order[idx + 1]

    @classmethod
    def validate_position_order(cls, player_count: int, phase: Phase, positions: list[Position]) -> bool:
        """
        Validate that a list of positions follows the correct betting order.

        Args:
            player_count: Number of players at the table
            phase: Current phase of the hand
            positions: List of positions to validate

        Returns:
            True if positions follow correct order, False otherwise
        """
        expected_order = cls.get_betting_order(player_count, phase)

        # Check if all expected positions are present
        if set(positions) != set(expected_order):
            return False

        # Check if order is exactly correct
        return positions == expected_order


# Convenience functions for common queries
def get_betting_order(num_players: int, phase: Phase, button_pos: Position = None) -> list[Position]:
    return BettingOrder.get_betting_order(num_players, phase, button_pos)


def get_first_to_act(player_count: int, phase: Phase) -> Position:
    return BettingOrder.get_first_to_act(player_count, phase)


def get_last_to_act(player_count: int, phase: Phase) -> Position:
    return BettingOrder.get_last_to_act(player_count, phase)
