import pytest
from pydantic import ValidationError

from note_extractor.midi.events import EventPosition
from note_extractor.splitter.notes import NoteDraft, SourceNote, finalize

START = EventPosition(tick=480, sequence=4)
KEY_END = EventPosition(tick=960, sequence=9)
RELEASE_END = EventPosition(tick=1200, sequence=12)


def test_a_draft_whose_ends_arrived_settles_into_a_note() -> None:
    note = finalize(_draft(key_end=KEY_END, release_end=RELEASE_END))

    assert note.source_id == 3
    assert note.channel == 0
    assert note.pitch == 60
    assert note.velocity == 100
    assert note.release_velocity == 20
    assert (note.start, note.key_end, note.release_end) == (START, KEY_END, RELEASE_END)


def test_a_note_states_the_spans_it_was_played_over() -> None:
    note = finalize(_draft(key_end=KEY_END, release_end=RELEASE_END))

    assert note.key_duration_ticks == 480
    assert note.release_duration_ticks == 720


@pytest.mark.parametrize(
    ("key_end", "release_end"),
    [(None, None), (KEY_END, None), (None, RELEASE_END)],
)
def test_a_draft_still_standing_open_is_reported(
    key_end: EventPosition | None,
    release_end: EventPosition | None,
) -> None:
    with pytest.raises(ValueError, match="note 3 stands open at tick 480"):
        finalize(_draft(key_end=key_end, release_end=release_end))


@pytest.mark.parametrize(
    ("key_end", "release_end"),
    [
        (EventPosition(tick=240, sequence=1), RELEASE_END),
        (KEY_END, EventPosition(tick=480, sequence=5)),
        (START, EventPosition(tick=479, sequence=99)),
    ],
)
def test_a_note_ending_before_it_starts_is_rejected(
    key_end: EventPosition,
    release_end: EventPosition,
) -> None:
    with pytest.raises(ValidationError, match="must end from its start onwards"):
        finalize(_draft(key_end=key_end, release_end=release_end))


def test_a_note_bounded_by_one_moment_throughout_is_accepted() -> None:
    """A key pressed and let go of at one moment is still a note the manifest can state."""
    note = finalize(_draft(key_end=START, release_end=START))

    assert note.key_duration_ticks == 0
    assert note.release_duration_ticks == 0


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("channel", 16),
        ("channel", -1),
        ("pitch", 128),
        ("velocity", 128),
        ("release_velocity", 200),
        ("source_id", -1),
    ],
)
def test_a_note_value_outside_the_midi_range_is_rejected(field: str, value: int) -> None:
    fields = {
        "source_id": 3,
        "channel": 0,
        "pitch": 60,
        "velocity": 100,
        "release_velocity": 20,
        "start": START,
        "key_end": KEY_END,
        "release_end": RELEASE_END,
    }

    with pytest.raises(ValidationError):
        SourceNote(**{**fields, field: value})  # type: ignore[arg-type]


def test_a_draft_opens_with_no_ends_and_a_silent_release() -> None:
    draft = NoteDraft(source_id=0, channel=0, pitch=60, velocity=100, start=START)

    assert draft.key_end is None
    assert draft.release_end is None
    assert draft.release_velocity == 0


def _draft(key_end: EventPosition | None, release_end: EventPosition | None) -> NoteDraft:
    return NoteDraft(
        source_id=3,
        channel=0,
        pitch=60,
        velocity=100,
        start=START,
        key_end=key_end,
        release_end=release_end,
        release_velocity=20,
    )
