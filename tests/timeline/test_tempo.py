from typing import Final

import pytest

from note_extractor.errors import ConfigurationError
from note_extractor.midi.events import EventPosition, TempoChange
from note_extractor.timeline.tempo import TempoMap, microseconds_per_beat, ticks_for_seconds

TICKS_PER_BEAT: Final = 480
TEMPO_120_BPM: Final = 500_000
TEMPO_150_BPM: Final = 400_000


def test_seconds_accumulate_across_a_mid_file_tempo_change() -> None:
    tempo_map = TempoMap(TICKS_PER_BEAT, [(0, TEMPO_120_BPM), (1920, TEMPO_150_BPM)])

    assert tempo_map.seconds_at(0) == pytest.approx(0.0)
    assert tempo_map.seconds_at(1920) == pytest.approx(2.0)
    assert tempo_map.seconds_at(2400) == pytest.approx(2.4)
    assert tempo_map.seconds_at(3840) == pytest.approx(3.6)


def test_seconds_between_spans_a_tempo_change() -> None:
    tempo_map = TempoMap(TICKS_PER_BEAT, [(0, TEMPO_120_BPM), (1920, TEMPO_150_BPM)])

    assert tempo_map.seconds_between(960, 2400) == pytest.approx(1.4)
    assert tempo_map.seconds_between(960, 1920) + tempo_map.seconds_between(1920, 2400) == pytest.approx(
        tempo_map.seconds_between(960, 2400)
    )


def test_the_default_tempo_holds_ahead_of_the_first_change() -> None:
    tempo_map = TempoMap(TICKS_PER_BEAT, [(1920, TEMPO_150_BPM)])

    assert tempo_map.seconds_at(960) == pytest.approx(1.0)
    assert tempo_map.seconds_at(2400) == pytest.approx(2.4)


def test_a_performance_without_tempo_changes_runs_at_the_default_tempo() -> None:
    tempo_map = TempoMap(TICKS_PER_BEAT, [])

    assert tempo_map.seconds_at(960) == pytest.approx(1.0)


def test_changes_are_read_from_performance_events() -> None:
    changes = (
        TempoChange(position=EventPosition(tick=0, sequence=0), microseconds_per_beat=TEMPO_120_BPM),
        TempoChange(position=EventPosition(tick=1920, sequence=9), microseconds_per_beat=TEMPO_150_BPM),
    )

    tempo_map = TempoMap.from_changes(TICKS_PER_BEAT, changes)

    assert tempo_map.seconds_at(2400) == pytest.approx(2.4)


def test_a_constant_map_holds_one_tempo() -> None:
    tempo_map = TempoMap.constant(TICKS_PER_BEAT, 115.0)

    assert tempo_map.seconds_at(TICKS_PER_BEAT) == pytest.approx(0.521_739)
    assert tempo_map.seconds_between(1920, 2400) == pytest.approx(0.521_739)


def test_beat_length_rounds_to_whole_microseconds() -> None:
    assert microseconds_per_beat(120.0) == 500_000
    assert microseconds_per_beat(115.0) == 521_739


def test_a_stretch_of_seconds_is_read_as_the_ticks_it_spans() -> None:
    assert ticks_for_seconds(1.0, TICKS_PER_BEAT, TEMPO_120_BPM) == 960
    assert ticks_for_seconds(5.0, TICKS_PER_BEAT, TEMPO_120_BPM) == 4800
    assert ticks_for_seconds(1.0, TICKS_PER_BEAT, TEMPO_150_BPM) == 1200


def test_a_stretch_of_no_seconds_spans_no_ticks() -> None:
    assert ticks_for_seconds(0.0, TICKS_PER_BEAT, TEMPO_120_BPM) == 0


@pytest.mark.parametrize(("seconds", "ticks"), [(0.5001, 480), (0.9999, 959), (0.0001, 0)])
def test_a_stretch_reaching_between_two_ticks_is_taken_down_to_the_one_it_reaches(
    seconds: float,
    ticks: int,
) -> None:
    """A bound written in seconds is held in ticks, so its ticks must never run past it."""
    assert ticks_for_seconds(seconds, TICKS_PER_BEAT, TEMPO_120_BPM) == ticks


@pytest.mark.parametrize("beats_per_minute", [0.0, -1.0])
def test_a_non_positive_tempo_is_rejected(beats_per_minute: float) -> None:
    with pytest.raises(ConfigurationError, match="tempo must be positive"):
        microseconds_per_beat(beats_per_minute)


def test_a_constant_map_rejects_a_non_positive_tempo() -> None:
    with pytest.raises(ConfigurationError, match="tempo must be positive"):
        TempoMap.constant(TICKS_PER_BEAT, 0.0)
