from __future__ import annotations

from bisect import bisect_left, bisect_right
from collections import defaultdict

from .models import ControllerEvent
from .timing import TempoMap

EventKey = tuple[int, int]


class ControllerTimeline:
    def __init__(self, events: tuple[ControllerEvent, ...]) -> None:
        by_control: dict[tuple[int, int], list[ControllerEvent]] = defaultdict(list)
        by_channel: dict[int, list[ControllerEvent]] = defaultdict(list)
        controls_by_channel: dict[int, set[int]] = defaultdict(set)

        for event in events:
            by_control[(event.channel, event.control)].append(event)
            by_channel[event.channel].append(event)
            controls_by_channel[event.channel].add(event.control)

        self.by_control = {key: tuple(value) for key, value in by_control.items()}
        self.by_channel = {key: tuple(value) for key, value in by_channel.items()}
        self.controls_by_channel = {
            key: frozenset(value) for key, value in controls_by_channel.items()
        }
        self._control_keys = {
            key: tuple(event.key for event in value)
            for key, value in self.by_control.items()
        }
        self._channel_keys = {
            key: tuple(event.key for event in value)
            for key, value in self.by_channel.items()
        }

    def value_before(self, channel: int, control: int, key: EventKey, default: int = 0) -> int:
        events = self.by_control.get((channel, control), ())
        keys = self._control_keys.get((channel, control), ())
        index = bisect_left(keys, key) - 1
        return events[index].value if index >= 0 else default

    def events_between(
        self,
        channels: set[int],
        start_key: EventKey,
        end_key: EventKey,
        ignored_controls: set[int] | None = None,
    ) -> list[ControllerEvent]:
        ignored = ignored_controls or set()
        result: list[ControllerEvent] = []

        for channel in channels:
            events = self.by_channel.get(channel, ())
            keys = self._channel_keys.get(channel, ())
            start = bisect_right(keys, start_key)
            end = bisect_right(keys, end_key)
            result.extend(
                event for event in events[start:end] if event.control not in ignored
            )

        result.sort(key=lambda event: event.key)
        return result

    def time_weighted_average(
        self,
        channel: int,
        control: int,
        start_key: EventKey,
        end_key: EventKey,
        tempo_map: TempoMap,
        default: int = 0,
    ) -> float:
        start_tick = start_key[0]
        end_tick = end_key[0]
        current_value = self.value_before(channel, control, start_key, default)
        events = self.events_between({channel}, start_key, end_key)
        events = [event for event in events if event.control == control]

        total_seconds = tempo_map.seconds_between(start_tick, end_tick)
        if total_seconds <= 0:
            return float(current_value)

        weighted = 0.0
        cursor_tick = start_tick
        for event in events:
            weighted += current_value * tempo_map.seconds_between(cursor_tick, event.tick)
            current_value = event.value
            cursor_tick = event.tick
        weighted += current_value * tempo_map.seconds_between(cursor_tick, end_tick)
        return weighted / total_seconds
