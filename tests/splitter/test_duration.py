import pytest

from note_extractor.midi.events import EventPosition
from note_extractor.splitter.duration import DurationBounds, sounded_notes
from note_extractor.splitter.notes import SourceNote

UNBOUNDED = DurationBounds(skip_below_ticks=0, minimum_ticks=0, maximum_ticks=None)


def _bounds(skip_below_ticks: int = 0, minimum_ticks: int = 0, maximum_ticks: int | None = None) -> DurationBounds:
    return DurationBounds(
        skip_below_ticks=skip_below_ticks,
        minimum_ticks=minimum_ticks,
        maximum_ticks=maximum_ticks,
    )


def test_a_run_stating_no_bounds_sounds_every_note_as_it_was_played() -> None:
    notes = [_note(source_id=0, key_ticks=120, release_ticks=240), _note(source_id=1, key_ticks=960, release_ticks=960)]

    assert sounded_notes(notes, UNBOUNDED) == tuple(notes)


def test_a_note_played_too_briefly_to_be_worth_sampling_is_left_out() -> None:
    notes = [_note(source_id=0, key_ticks=120, release_ticks=240), _note(source_id=1, key_ticks=480, release_ticks=960)]

    sounded = sounded_notes(notes, _bounds(skip_below_ticks=480))

    assert [note.source_id for note in sounded] == [1]


def test_a_note_played_over_exactly_the_briefest_span_is_kept() -> None:
    """The briefest span is the briefest a note may be played, not the briefest it must outlast."""
    notes = [_note(source_id=0, key_ticks=480, release_ticks=480)]

    assert sounded_notes(notes, _bounds(skip_below_ticks=480))


def test_a_note_the_run_leaves_out_keeps_the_place_the_others_were_played_from() -> None:
    """Source ids order the notes by the order their keys were pressed, whichever a run takes."""
    notes = [
        _note(source_id=0, key_ticks=960, release_ticks=960),
        _note(source_id=1, key_ticks=120, release_ticks=120),
        _note(source_id=2, key_ticks=960, release_ticks=960),
    ]

    assert [note.source_id for note in sounded_notes(notes, _bounds(skip_below_ticks=480))] == [0, 2]


def test_a_note_sounding_less_than_the_shortest_span_is_held_on_until_it_reaches_it() -> None:
    notes = [_note(source_id=0, key_ticks=120, release_ticks=240)]

    sounded = sounded_notes(notes, _bounds(minimum_ticks=960))

    assert sounded[0].release_end.tick == 960
    assert sounded[0].release_duration_ticks == 960


def test_a_note_held_on_keeps_its_key_down_to_the_end_of_the_span() -> None:
    """A key held down is what carries the sound on; the pedal was let up where it was played."""
    notes = [_note(source_id=0, key_ticks=120, release_ticks=480)]

    sounded = sounded_notes(notes, _bounds(minimum_ticks=960))

    assert sounded[0].key_end == sounded[0].release_end
    assert sounded[0].key_duration_ticks == 960


def test_a_note_held_on_sits_ahead_of_everything_carrying_the_tick_it_ends_on() -> None:
    """A controller posted where the note is let go of belongs to what comes after it."""
    notes = [_note(source_id=0, key_ticks=120, release_ticks=240)]

    sounded = sounded_notes(notes, _bounds(minimum_ticks=960))

    assert sounded[0].release_end == EventPosition.at_tick_start(960)


def test_a_note_already_sounding_the_shortest_span_is_left_as_it_was_played() -> None:
    note = _note(source_id=0, key_ticks=480, release_ticks=960)

    assert sounded_notes([note], _bounds(minimum_ticks=960)) == (note,)


def test_a_note_played_too_briefly_is_left_out_rather_than_held_on() -> None:
    """The two spans read the same note at different moments: as it was played, then as it sounds."""
    notes = [_note(source_id=0, key_ticks=60, release_ticks=60), _note(source_id=1, key_ticks=300, release_ticks=300)]

    sounded = sounded_notes(notes, _bounds(skip_below_ticks=240, minimum_ticks=960))

    assert [note.source_id for note in sounded] == [1]
    assert sounded[0].release_duration_ticks == 960


def test_a_note_outlasting_the_longest_span_is_let_go_of_where_that_span_runs_out() -> None:
    notes = [_note(source_id=0, key_ticks=480, release_ticks=2400)]

    sounded = sounded_notes(notes, _bounds(maximum_ticks=960))

    assert sounded[0].release_end.tick == 960
    assert sounded[0].release_duration_ticks == 960


def test_a_note_sounding_within_the_longest_span_is_left_as_it_was_played() -> None:
    note = _note(source_id=0, key_ticks=480, release_ticks=960)

    assert sounded_notes([note], _bounds(maximum_ticks=960)) == (note,)


def test_a_key_still_down_where_the_longest_span_runs_out_comes_up_there_too() -> None:
    """A key outlasting the sound would leave the note ending after it was let go of."""
    notes = [_note(source_id=0, key_ticks=2400, release_ticks=2400)]

    sounded = sounded_notes(notes, _bounds(maximum_ticks=960))

    assert sounded[0].key_end.tick == 960
    assert sounded[0].key_duration_ticks == 960


def test_a_key_released_ahead_of_the_longest_span_keeps_the_moment_it_came_up() -> None:
    notes = [_note(source_id=0, key_ticks=480, release_ticks=2400)]

    sounded = sounded_notes(notes, _bounds(maximum_ticks=960))

    assert sounded[0].key_end == EventPosition(tick=480, sequence=10)


def test_a_note_let_go_of_early_sits_ahead_of_everything_carrying_the_tick_it_ends_on() -> None:
    """A controller posted where the note is let go of belongs to what comes after it."""
    notes = [_note(source_id=0, key_ticks=2400, release_ticks=2400)]

    sounded = sounded_notes(notes, _bounds(maximum_ticks=960))

    assert sounded[0].release_end == EventPosition.at_tick_start(960)


def test_a_run_stating_both_spans_brings_every_note_it_keeps_between_them() -> None:
    notes = [
        _note(source_id=0, key_ticks=240, release_ticks=240),
        _note(source_id=1, key_ticks=1200, release_ticks=1200),
        _note(source_id=2, key_ticks=4800, release_ticks=4800),
    ]

    sounded = sounded_notes(notes, _bounds(minimum_ticks=960, maximum_ticks=1920))

    assert [note.release_duration_ticks for note in sounded] == [960, 1200, 1920]


@pytest.mark.parametrize(("key_ticks", "release_ticks"), [(2400, 2400), (120, 240)])
def test_a_note_the_run_sounds_for_itself_keeps_everything_it_was_played_with(
    key_ticks: int,
    release_ticks: int,
) -> None:
    notes = [_note(source_id=3, key_ticks=key_ticks, release_ticks=release_ticks)]

    sounded = sounded_notes(notes, _bounds(minimum_ticks=960, maximum_ticks=960))

    assert (sounded[0].source_id, sounded[0].channel, sounded[0].pitch) == (3, 0, 60)
    assert (sounded[0].velocity, sounded[0].release_velocity) == (100, 20)
    assert sounded[0].start == notes[0].start


@pytest.mark.parametrize("skip_below_ticks", [961, 1920])
def test_a_run_taking_nothing_from_a_performance_sounds_no_notes(skip_below_ticks: int) -> None:
    notes = [_note(source_id=0, key_ticks=960, release_ticks=960)]

    assert sounded_notes(notes, _bounds(skip_below_ticks=skip_below_ticks)) == ()


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
