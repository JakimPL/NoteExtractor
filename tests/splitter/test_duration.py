import pytest

from note_extractor.midi.events import EventPosition
from note_extractor.splitter.duration import DurationBounds, sounded_notes
from note_extractor.splitter.notes import SourceNote

UNBOUNDED = DurationBounds(minimum_ticks=0, maximum_ticks=None)


def test_a_run_stating_no_bounds_sounds_every_note_as_it_was_played() -> None:
    notes = [_note(source_id=0, key_ticks=120, release_ticks=240), _note(source_id=1, key_ticks=960, release_ticks=960)]

    assert sounded_notes(notes, UNBOUNDED) == tuple(notes)


def test_a_note_too_short_to_be_worth_a_sample_is_left_out() -> None:
    notes = [_note(source_id=0, key_ticks=120, release_ticks=240), _note(source_id=1, key_ticks=480, release_ticks=960)]

    sounded = sounded_notes(notes, DurationBounds(minimum_ticks=480, maximum_ticks=None))

    assert [note.source_id for note in sounded] == [1]


def test_a_note_sounding_exactly_the_shortest_span_is_kept() -> None:
    """The shortest span is the shortest a note may sound, not the shortest it must outlast."""
    notes = [_note(source_id=0, key_ticks=480, release_ticks=480)]

    assert sounded_notes(notes, DurationBounds(minimum_ticks=480, maximum_ticks=None))


def test_a_note_the_run_leaves_out_keeps_the_place_the_others_were_played_from() -> None:
    """Source ids order the notes by the order their keys were pressed, whichever a run takes."""
    notes = [
        _note(source_id=0, key_ticks=960, release_ticks=960),
        _note(source_id=1, key_ticks=120, release_ticks=120),
        _note(source_id=2, key_ticks=960, release_ticks=960),
    ]

    assert [note.source_id for note in sounded_notes(notes, DurationBounds(minimum_ticks=480, maximum_ticks=None))] == [
        0,
        2,
    ]


def test_a_note_outlasting_the_longest_span_is_let_go_of_where_that_span_runs_out() -> None:
    notes = [_note(source_id=0, key_ticks=480, release_ticks=2400)]

    sounded = sounded_notes(notes, DurationBounds(minimum_ticks=0, maximum_ticks=960))

    assert sounded[0].release_end.tick == 960
    assert sounded[0].release_duration_ticks == 960


def test_a_note_sounding_within_the_longest_span_is_left_as_it_was_played() -> None:
    note = _note(source_id=0, key_ticks=480, release_ticks=960)

    assert sounded_notes([note], DurationBounds(minimum_ticks=0, maximum_ticks=960)) == (note,)


def test_a_key_still_down_where_the_longest_span_runs_out_comes_up_there_too() -> None:
    """A key outlasting the sound would leave the note ending after it was let go of."""
    notes = [_note(source_id=0, key_ticks=2400, release_ticks=2400)]

    sounded = sounded_notes(notes, DurationBounds(minimum_ticks=0, maximum_ticks=960))

    assert sounded[0].key_end.tick == 960
    assert sounded[0].key_duration_ticks == 960


def test_a_key_released_ahead_of_the_longest_span_keeps_the_moment_it_came_up() -> None:
    notes = [_note(source_id=0, key_ticks=480, release_ticks=2400)]

    sounded = sounded_notes(notes, DurationBounds(minimum_ticks=0, maximum_ticks=960))

    assert sounded[0].key_end == EventPosition(tick=480, sequence=10)


def test_a_note_let_go_of_early_sits_ahead_of_everything_carrying_the_tick_it_ends_on() -> None:
    """A controller posted where the note is let go of belongs to what comes after it."""
    notes = [_note(source_id=0, key_ticks=2400, release_ticks=2400)]

    sounded = sounded_notes(notes, DurationBounds(minimum_ticks=0, maximum_ticks=960))

    assert sounded[0].release_end == EventPosition.at_tick_start(960)


def test_a_note_cut_short_keeps_everything_it_was_played_with() -> None:
    notes = [_note(source_id=3, key_ticks=2400, release_ticks=2400)]

    sounded = sounded_notes(notes, DurationBounds(minimum_ticks=0, maximum_ticks=960))

    assert (sounded[0].source_id, sounded[0].channel, sounded[0].pitch) == (3, 0, 60)
    assert (sounded[0].velocity, sounded[0].release_velocity) == (100, 20)
    assert sounded[0].start == notes[0].start


@pytest.mark.parametrize("minimum_ticks", [961, 1920])
def test_a_run_taking_nothing_from_a_performance_sounds_no_notes(minimum_ticks: int) -> None:
    notes = [_note(source_id=0, key_ticks=960, release_ticks=960)]

    assert sounded_notes(notes, DurationBounds(minimum_ticks=minimum_ticks, maximum_ticks=None)) == ()


def _note(source_id: int, key_ticks: int, release_ticks: int) -> SourceNote:
    return SourceNote(
        source_id=source_id,
        channel=0,
        pitch=60,
        velocity=100,
        release_velocity=20,
        start=EventPosition(tick=0, sequence=0),
        key_end=EventPosition(tick=key_ticks, sequence=10),
        release_end=EventPosition(tick=release_ticks, sequence=20),
    )
