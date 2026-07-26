from typing import Final

import pytest

from note_extractor.midi.events import ControlChange, EventPosition
from note_extractor.splitter.cc_averages import average_control_values, time_weighted_average
from note_extractor.splitter.controllers import ControllerTimeline
from note_extractor.splitter.notes import SourceNote
from note_extractor.timeline.tempo import TempoMap

TICKS_PER_BEAT: Final = 480
MODULATION: Final = 1
EXPRESSION: Final = 11


def test_a_controller_held_throughout_averages_to_the_value_it_held() -> None:
    timeline = ControllerTimeline(
        [_posted(tick=0, sequence=0, control=MODULATION, value=40)],
    )

    assert time_weighted_average(timeline, _steady_tempo(), _note(0, 960, start_sequence=5), MODULATION) == 40.0


def test_a_controller_posting_nothing_averages_to_the_value_a_receiver_starts_from() -> None:
    timeline = ControllerTimeline([])

    assert time_weighted_average(timeline, _steady_tempo(), _note(0, 960, start_sequence=5), MODULATION) == 0.0


def test_a_controller_changing_halfway_averages_the_two_values_evenly() -> None:
    timeline = ControllerTimeline(
        [
            _posted(tick=0, sequence=0, control=MODULATION, value=100),
            _posted(tick=480, sequence=2, control=MODULATION, value=0),
        ],
    )

    assert time_weighted_average(timeline, _steady_tempo(), _note(0, 960, start_sequence=1), MODULATION) == 50.0


def test_a_controller_changing_late_counts_for_the_stretch_it_held() -> None:
    timeline = ControllerTimeline(
        [
            _posted(tick=0, sequence=0, control=MODULATION, value=80),
            _posted(tick=720, sequence=2, control=MODULATION, value=0),
        ],
    )

    average = time_weighted_average(timeline, _steady_tempo(), _note(0, 960, start_sequence=1), MODULATION)

    assert average == pytest.approx(60.0)


def test_a_stretch_crossing_a_tempo_change_weighs_each_half_by_the_time_it_took() -> None:
    """The first half of the note runs at half the speed, so its value is heard for twice as long."""
    timeline = ControllerTimeline(
        [
            _posted(tick=0, sequence=0, control=MODULATION, value=120),
            _posted(tick=480, sequence=2, control=MODULATION, value=0),
        ],
    )
    tempo = TempoMap(TICKS_PER_BEAT, [(0, 1_000_000), (480, 500_000)])

    assert tempo.seconds_between(0, 480) == pytest.approx(1.0)
    assert tempo.seconds_between(480, 960) == pytest.approx(0.5)
    assert time_weighted_average(timeline, tempo, _note(0, 960, start_sequence=1), MODULATION) == pytest.approx(80.0)


def test_a_note_sounding_over_no_time_reads_the_value_holding_at_its_onset() -> None:
    timeline = ControllerTimeline(
        [
            _posted(tick=0, sequence=0, control=MODULATION, value=70),
            _posted(tick=480, sequence=3, control=MODULATION, value=10),
        ],
    )

    assert time_weighted_average(timeline, _steady_tempo(), _note(480, 480, start_sequence=1), MODULATION) == 70.0


def test_a_value_posted_at_the_onset_counts_from_the_onset_onwards() -> None:
    """A message on the onset tick arrives after the note starts, so it holds for the whole stretch."""
    timeline = ControllerTimeline(
        [
            _posted(tick=0, sequence=0, control=MODULATION, value=100),
            _posted(tick=480, sequence=9, control=MODULATION, value=0),
        ],
    )

    assert time_weighted_average(timeline, _steady_tempo(), _note(480, 960, start_sequence=1), MODULATION) == 0.0


def test_each_tracked_controller_is_averaged_in_the_order_it_was_asked_for() -> None:
    timeline = ControllerTimeline(
        [
            _posted(tick=0, sequence=0, control=MODULATION, value=40),
            _posted(tick=0, sequence=1, control=EXPRESSION, value=90),
        ],
    )

    note = _note(0, 960, start_sequence=5)

    averages = average_control_values(timeline, _steady_tempo(), note, (MODULATION, EXPRESSION))

    assert list(averages) == [MODULATION, EXPRESSION]
    assert averages == {MODULATION: 40.0, EXPRESSION: 90.0}


def _steady_tempo() -> TempoMap:
    return TempoMap(TICKS_PER_BEAT, [(0, 500_000)])


def _posted(tick: int, sequence: int, control: int, value: int) -> ControlChange:
    return ControlChange(
        position=EventPosition(tick=tick, sequence=sequence),
        channel=0,
        control=control,
        value=value,
    )


def _note(start_tick: int, release_end_tick: int, start_sequence: int) -> SourceNote:
    """One note sounding between the two ticks, pressed at the given place in the stream."""
    return SourceNote(
        source_id=0,
        channel=0,
        pitch=60,
        velocity=100,
        release_velocity=0,
        start=EventPosition(tick=start_tick, sequence=start_sequence),
        key_end=EventPosition(tick=release_end_tick, sequence=20),
        release_end=EventPosition(tick=release_end_tick, sequence=20),
    )
