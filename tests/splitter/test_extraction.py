from mido import Message

from note_extractor.midi.events import ControlChange, EventPosition
from note_extractor.splitter.extraction import NoteExtractor, SustainPedalState
from note_extractor.splitter.notes import NoteDraft

from .conftest import ReadPerformance


def test_a_key_released_while_the_pedal_is_up_ends_where_it_was_released(
    read_performance: ReadPerformance,
) -> None:
    drafts = _extract(
        read_performance,
        [
            Message("note_on", channel=0, note=60, velocity=100, time=0),
            Message("note_off", channel=0, note=60, velocity=20, time=480),
        ],
        sustain_pedal=True,
    )

    assert _spans(drafts) == [(0, 480, 480)]
    assert drafts[0].release_velocity == 20


def test_a_key_released_while_the_pedal_is_down_sounds_until_the_pedal_comes_up(
    read_performance: ReadPerformance,
) -> None:
    drafts = _extract(
        read_performance,
        [
            Message("control_change", channel=0, control=64, value=127, time=0),
            Message("note_on", channel=0, note=60, velocity=100, time=0),
            Message("note_off", channel=0, note=60, velocity=20, time=480),
            Message("control_change", channel=0, control=64, value=0, time=240),
        ],
        sustain_pedal=True,
    )

    assert _spans(drafts) == [(0, 480, 720)]


def test_a_pedal_held_to_the_end_of_the_performance_sounds_to_that_end(
    read_performance: ReadPerformance,
) -> None:
    drafts = _extract(
        read_performance,
        [
            Message("control_change", channel=0, control=64, value=127, time=0),
            Message("note_on", channel=0, note=60, velocity=100, time=0),
            Message("note_off", channel=0, note=60, velocity=20, time=480),
            Message("control_change", channel=0, control=1, value=90, time=240),
        ],
        sustain_pedal=True,
    )

    assert _spans(drafts) == [(0, 480, 720)]


def test_a_run_leaving_the_pedal_alone_ends_every_note_at_its_key_release(
    read_performance: ReadPerformance,
) -> None:
    drafts = _extract(
        read_performance,
        [
            Message("control_change", channel=0, control=64, value=127, time=0),
            Message("note_on", channel=0, note=60, velocity=100, time=0),
            Message("note_off", channel=0, note=60, velocity=20, time=480),
            Message("control_change", channel=0, control=64, value=0, time=240),
        ],
        sustain_pedal=False,
    )

    assert _spans(drafts) == [(0, 480, 480)]


def test_a_key_never_released_sounds_to_the_end_of_the_performance(
    read_performance: ReadPerformance,
) -> None:
    drafts = _extract(
        read_performance,
        [
            Message("note_on", channel=0, note=60, velocity=100, time=0),
            Message("control_change", channel=0, control=1, value=90, time=480),
        ],
        sustain_pedal=True,
    )

    assert _spans(drafts) == [(0, 480, 480)]
    assert drafts[0].release_velocity == 0


def test_repeated_presses_of_one_key_pair_up_with_its_releases_in_turn(
    read_performance: ReadPerformance,
) -> None:
    drafts = _extract(
        read_performance,
        [
            Message("note_on", channel=0, note=60, velocity=100, time=0),
            Message("note_on", channel=0, note=60, velocity=100, time=120),
            Message("note_off", channel=0, note=60, velocity=20, time=120),
            Message("note_off", channel=0, note=60, velocity=30, time=120),
        ],
        sustain_pedal=True,
    )

    assert _spans(drafts) == [(0, 240, 240), (120, 360, 360)]
    assert [draft.release_velocity for draft in drafts] == [20, 30]


def test_a_release_matching_no_press_leaves_the_performance_unchanged(
    read_performance: ReadPerformance,
) -> None:
    drafts = _extract(
        read_performance,
        [
            Message("note_off", channel=0, note=60, velocity=0, time=0),
            Message("note_on", channel=0, note=60, velocity=90, time=240),
            Message("note_off", channel=0, note=60, velocity=10, time=240),
        ],
        sustain_pedal=True,
    )

    assert _spans(drafts) == [(240, 480, 480)]


def test_a_press_of_no_force_releases_the_key_it_names(read_performance: ReadPerformance) -> None:
    """A `note_on` of zero velocity is how many sequencers write a key release."""
    drafts = _extract(
        read_performance,
        [
            Message("note_on", channel=0, note=60, velocity=100, time=0),
            Message("note_on", channel=0, note=60, velocity=0, time=480),
        ],
        sustain_pedal=True,
    )

    assert _spans(drafts) == [(0, 480, 480)]


def test_a_pedal_held_on_one_channel_leaves_the_other_channels_alone(
    read_performance: ReadPerformance,
) -> None:
    drafts = _extract(
        read_performance,
        [
            Message("control_change", channel=0, control=64, value=127, time=0),
            Message("note_on", channel=0, note=60, velocity=100, time=0),
            Message("note_on", channel=1, note=48, velocity=70, time=0),
            Message("note_off", channel=0, note=60, velocity=20, time=480),
            Message("note_off", channel=1, note=48, velocity=20, time=0),
            Message("control_change", channel=0, control=64, value=0, time=240),
        ],
        sustain_pedal=True,
    )

    assert _spans(drafts) == [(0, 480, 720), (0, 480, 480)]


def test_notes_are_read_in_the_order_their_keys_were_pressed(
    read_performance: ReadPerformance,
) -> None:
    drafts = _extract(
        read_performance,
        [
            Message("note_on", channel=0, note=67, velocity=80, time=0),
            Message("note_on", channel=0, note=60, velocity=100, time=0),
            Message("note_off", channel=0, note=60, velocity=20, time=480),
            Message("note_off", channel=0, note=67, velocity=20, time=0),
        ],
        sustain_pedal=True,
    )

    assert [(draft.source_id, draft.pitch) for draft in drafts] == [(0, 67), (1, 60)]


def test_a_pedal_pressed_past_the_threshold_counts_as_held() -> None:
    pedal = SustainPedalState()

    assert pedal.is_down(0) is False
    assert pedal.take(_pedal_message(63)) is False
    assert pedal.is_down(0) is False
    assert pedal.take(_pedal_message(64)) is False
    assert pedal.is_down(0) is True


def test_only_the_message_letting_a_held_pedal_up_reports_a_release() -> None:
    pedal = SustainPedalState()
    pedal.take(_pedal_message(127))

    assert pedal.take(_pedal_message(127)) is False
    assert pedal.take(_pedal_message(0)) is True
    assert pedal.take(_pedal_message(0)) is False


def _pedal_message(value: int) -> ControlChange:
    return ControlChange(position=EventPosition(tick=0, sequence=0), channel=0, control=64, value=value)


def _extract(
    read_performance: ReadPerformance,
    messages: list[Message],
    sustain_pedal: bool,
) -> tuple[NoteDraft, ...]:
    return NoteExtractor(sustain_pedal).extract(read_performance(messages))


def _spans(drafts: tuple[NoteDraft, ...]) -> list[tuple[int, int, int]]:
    """Start, key end, and release end tick of each note, in the order they were read."""
    return [
        (
            draft.start.tick,
            draft.key_end.tick if draft.key_end is not None else -1,
            draft.release_end.tick if draft.release_end is not None else -1,
        )
        for draft in drafts
    ]
