from bisect import bisect_left, bisect_right
from collections.abc import Sequence
from collections.abc import Set as AbstractSet
from typing import Final

from ..midi.events import ControlChange, EventPosition

INITIAL_CONTROLLER_VALUE: Final = 0


class ControllerTimeline:
    """Controller messages of one performance, indexed for lookup by position.

    Lookups run by channel and by control, which is what lets the arrangement read the value a
    controller held at a note's onset and copy the messages arriving while that note sounds.
    """

    def __init__(self, events: Sequence[ControlChange]) -> None:
        by_control: dict[tuple[int, int], list[ControlChange]] = {}
        by_channel: dict[int, list[ControlChange]] = {}
        for event in events:
            by_control.setdefault((event.channel, event.control), []).append(event)
            by_channel.setdefault(event.channel, []).append(event)

        self._by_control = {key: tuple(found) for key, found in by_control.items()}
        self._by_channel = {key: tuple(found) for key, found in by_channel.items()}
        self._control_positions = {key: _positions(found) for key, found in self._by_control.items()}
        self._channel_positions = {key: _positions(found) for key, found in self._by_channel.items()}

    def value_before(self, channel: int, control: int, position: EventPosition) -> int:
        """Value one controller held ahead of the given position.

        A performance posting nothing for that controller beforehand reads as
        `INITIAL_CONTROLLER_VALUE`, the value a receiver starts from.
        """
        events = self._by_control.get((channel, control), ())
        index = bisect_left(self._control_positions.get((channel, control), ()), position) - 1
        return events[index].value if index >= 0 else INITIAL_CONTROLLER_VALUE

    def events_between(
        self,
        channels: AbstractSet[int],
        start: EventPosition,
        end: EventPosition,
        ignored_controls: AbstractSet[int],
    ) -> tuple[ControlChange, ...]:
        """Messages the given channels post after `start` and up to `end`, in stream order."""
        found: list[ControlChange] = []
        for channel in sorted(channels):
            events = _between(
                self._by_channel.get(channel, ()),
                self._channel_positions.get(channel, ()),
                start,
                end,
            )
            found.extend(event for event in events if event.control not in ignored_controls)

        return tuple(sorted(found, key=lambda event: event.position))

    def control_events_between(
        self,
        channel: int,
        control: int,
        start: EventPosition,
        end: EventPosition,
    ) -> tuple[ControlChange, ...]:
        """Messages one controller posts after `start` and up to `end`, in stream order."""
        return _between(
            self._by_control.get((channel, control), ()),
            self._control_positions.get((channel, control), ()),
            start,
            end,
        )


def _positions(events: Sequence[ControlChange]) -> tuple[EventPosition, ...]:
    """Positions of the given messages, ordered for lookup by bisection."""
    return tuple(event.position for event in events)


def _between(
    events: Sequence[ControlChange],
    positions: Sequence[EventPosition],
    start: EventPosition,
    end: EventPosition,
) -> tuple[ControlChange, ...]:
    """Messages sitting after `start` and up to `end`, taken from one ordered run of messages."""
    return tuple(events[bisect_right(positions, start) : bisect_right(positions, end)])
