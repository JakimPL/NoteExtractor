from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
from fractions import Fraction

from mido import bpm2tempo

from .models import TimedMessage


@dataclass(frozen=True, slots=True)
class TempoPoint:
    tick: int
    tempo: int
    seconds: float


class TempoMap:
    def __init__(self, ticks_per_beat: int, changes: list[tuple[int, int]]) -> None:
        self.ticks_per_beat = ticks_per_beat
        normalized = _normalize_changes(changes, 500_000)
        points: list[TempoPoint] = []
        seconds = 0.0
        previous_tick, previous_value = normalized[0]
        points.append(TempoPoint(previous_tick, previous_value, seconds))

        for tick, value in normalized[1:]:
            seconds += _ticks_to_seconds(tick - previous_tick, ticks_per_beat, previous_value)
            points.append(TempoPoint(tick, value, seconds))
            previous_tick = tick
            previous_value = value

        self.points = tuple(points)
        self._ticks = tuple(point.tick for point in points)

    @classmethod
    def from_events(cls, ticks_per_beat: int, events: tuple[TimedMessage, ...]) -> TempoMap:
        changes = [
            (event.tick, event.message.tempo)
            for event in events
            if event.message.type == "set_tempo"
        ]
        return cls(ticks_per_beat, changes)

    @classmethod
    def constant(cls, ticks_per_beat: int, bpm: float) -> TempoMap:
        return cls(ticks_per_beat, [(0, bpm2tempo(bpm))])

    def seconds_at(self, tick: int) -> float:
        index = bisect_right(self._ticks, tick) - 1
        point = self.points[index]
        return point.seconds + _ticks_to_seconds(
            tick - point.tick,
            self.ticks_per_beat,
            point.tempo,
        )

    def seconds_between(self, start_tick: int, end_tick: int) -> float:
        return self.seconds_at(end_tick) - self.seconds_at(start_tick)


@dataclass(frozen=True, slots=True)
class SignaturePoint:
    tick: int
    numerator: int
    denominator: int
    measures: float


class TimeSignatureMap:
    def __init__(
        self,
        ticks_per_beat: int,
        changes: list[tuple[int, tuple[int, int]]],
    ) -> None:
        self.ticks_per_beat = ticks_per_beat
        normalized = _normalize_changes(changes, (4, 4))
        points: list[SignaturePoint] = []
        measures = Fraction(0)
        previous_tick, previous_signature = normalized[0]
        points.append(
            SignaturePoint(
                previous_tick,
                previous_signature[0],
                previous_signature[1],
                float(measures),
            )
        )

        for tick, signature in normalized[1:]:
            measures += Fraction(tick - previous_tick, 1) / _measure_ticks_fraction(
                ticks_per_beat,
                previous_signature[0],
                previous_signature[1],
            )
            points.append(
                SignaturePoint(tick, signature[0], signature[1], float(measures))
            )
            previous_tick = tick
            previous_signature = signature

        self.points = tuple(points)
        self._ticks = tuple(point.tick for point in points)

    @classmethod
    def from_events(
        cls,
        ticks_per_beat: int,
        events: tuple[TimedMessage, ...],
    ) -> TimeSignatureMap:
        changes = [
            (event.tick, (event.message.numerator, event.message.denominator))
            for event in events
            if event.message.type == "time_signature"
        ]
        return cls(ticks_per_beat, changes)

    @classmethod
    def constant(
        cls,
        ticks_per_beat: int,
        numerator: int,
        denominator: int,
    ) -> TimeSignatureMap:
        return cls(ticks_per_beat, [(0, (numerator, denominator))])

    def measures_at(self, tick: int) -> float:
        index = bisect_right(self._ticks, tick) - 1
        point = self.points[index]
        measure_ticks = _measure_ticks_fraction(
            self.ticks_per_beat,
            point.numerator,
            point.denominator,
        )
        return point.measures + float(Fraction(tick - point.tick, 1) / measure_ticks)

    def measures_between(self, start_tick: int, end_tick: int) -> float:
        return self.measures_at(end_tick) - self.measures_at(start_tick)

    def ticks_for_measures(self, measures: float) -> int:
        point = self.points[0]
        ticks = float(
            _measure_ticks_fraction(
                self.ticks_per_beat,
                point.numerator,
                point.denominator,
            )
        ) * measures
        return round(ticks)


def parse_time_signature(value: str) -> tuple[int, int]:
    try:
        numerator_text, denominator_text = value.split("/", maxsplit=1)
        numerator = int(numerator_text)
        denominator = int(denominator_text)
    except (ValueError, TypeError) as exc:
        raise ValueError("time signature must look like 4/4") from exc

    if numerator <= 0:
        raise ValueError("time signature numerator must be positive")
    if denominator <= 0 or denominator & (denominator - 1):
        raise ValueError("time signature denominator must be a power of two")
    return numerator, denominator


def _normalize_changes(changes: list[tuple[int, object]], default: object) -> list[tuple[int, object]]:
    by_tick: dict[int, object] = {0: default}
    for tick, value in changes:
        by_tick[tick] = value
    return sorted(by_tick.items())


def _ticks_to_seconds(ticks: int, ticks_per_beat: int, tempo: int) -> float:
    return ticks * tempo / 1_000_000 / ticks_per_beat


def _measure_ticks_fraction(
    ticks_per_beat: int,
    numerator: int,
    denominator: int,
) -> Fraction:
    return Fraction(ticks_per_beat * numerator * 4, denominator)
