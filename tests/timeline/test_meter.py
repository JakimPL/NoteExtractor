from fractions import Fraction
from typing import Final

import pytest

from note_extractor.errors import ConfigurationError
from note_extractor.midi.events import EventPosition, MeterChange
from note_extractor.timeline.meter import (
    DEFAULT_SIGNATURE,
    ConstantMeter,
    MeterMap,
    TimeSignature,
)

TICKS_PER_BEAT: Final = 480
COMMON_TIME: Final = TimeSignature(numerator=4, denominator=4)
THREE_EIGHTHS: Final = TimeSignature(numerator=3, denominator=8)


def test_measures_accumulate_across_a_mid_file_signature_change() -> None:
    meter_map = MeterMap(TICKS_PER_BEAT, [(0, COMMON_TIME), (3840, THREE_EIGHTHS)])

    assert meter_map.measures_at(0) == pytest.approx(0.0)
    assert meter_map.measures_at(1920) == pytest.approx(1.0)
    assert meter_map.measures_at(3840) == pytest.approx(2.0)
    assert meter_map.measures_at(4560) == pytest.approx(3.0)


def test_measures_between_spans_a_signature_change() -> None:
    meter_map = MeterMap(TICKS_PER_BEAT, [(0, COMMON_TIME), (3840, THREE_EIGHTHS)])

    assert meter_map.measures_between(1920, 4560) == pytest.approx(2.0)
    assert meter_map.measures_between(1920, 3840) + meter_map.measures_between(3840, 4560) == pytest.approx(
        meter_map.measures_between(1920, 4560)
    )


def test_the_default_signature_holds_ahead_of_the_first_change() -> None:
    meter_map = MeterMap(TICKS_PER_BEAT, [(3840, THREE_EIGHTHS)])

    assert meter_map.meter_at(0).signature == DEFAULT_SIGNATURE
    assert meter_map.measures_at(1920) == pytest.approx(1.0)


def test_meter_at_reads_the_signature_holding_on_a_tick() -> None:
    meter_map = MeterMap(TICKS_PER_BEAT, [(0, COMMON_TIME), (3840, THREE_EIGHTHS)])

    assert meter_map.meter_at(3839) == ConstantMeter(ticks_per_beat=TICKS_PER_BEAT, signature=COMMON_TIME)
    assert meter_map.meter_at(3840) == ConstantMeter(ticks_per_beat=TICKS_PER_BEAT, signature=THREE_EIGHTHS)


def test_changes_are_read_from_performance_events() -> None:
    changes = (
        MeterChange(position=EventPosition(tick=0, sequence=0), numerator=4, denominator=4),
        MeterChange(position=EventPosition(tick=3840, sequence=7), numerator=3, denominator=8),
    )

    meter_map = MeterMap.from_changes(TICKS_PER_BEAT, changes)

    assert meter_map.measures_at(4560) == pytest.approx(3.0)


def test_a_constant_map_holds_one_signature() -> None:
    meter_map = MeterMap.constant(TICKS_PER_BEAT, THREE_EIGHTHS)

    assert meter_map.measures_at(720) == pytest.approx(1.0)
    assert meter_map.measures_between(720, 1440) == pytest.approx(1.0)


def test_measure_ticks_follow_the_signature() -> None:
    assert ConstantMeter(ticks_per_beat=TICKS_PER_BEAT, signature=COMMON_TIME).measure_ticks == Fraction(1920)
    assert ConstantMeter(ticks_per_beat=TICKS_PER_BEAT, signature=THREE_EIGHTHS).measure_ticks == Fraction(720)


def test_ticks_for_measures_rounds_to_whole_ticks() -> None:
    meter = ConstantMeter(ticks_per_beat=TICKS_PER_BEAT, signature=COMMON_TIME)

    assert meter.ticks_for_measures(0.0) == 0
    assert meter.ticks_for_measures(0.25) == 480
    assert meter.ticks_for_measures(2.5) == 4800
    assert meter.ticks_for_measures(1 / 3) == 640


def test_measures_for_ticks_reads_a_span_as_a_share_of_a_measure() -> None:
    meter = ConstantMeter(ticks_per_beat=TICKS_PER_BEAT, signature=THREE_EIGHTHS)

    assert meter.measures_for_ticks(360) == pytest.approx(0.5)
    assert meter.measures_for_ticks(720) == pytest.approx(1.0)


@pytest.mark.parametrize(("numerator", "denominator"), [(0, 4), (-3, 4), (4, 0), (4, -8)])
def test_a_signature_outside_the_supported_range_is_rejected(numerator: int, denominator: int) -> None:
    with pytest.raises(ConfigurationError, match="time signature"):
        TimeSignature(numerator=numerator, denominator=denominator)
