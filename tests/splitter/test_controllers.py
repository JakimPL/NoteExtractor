from typing import Final

from note_extractor.midi.events import ControlChange, EventPosition
from note_extractor.splitter.controllers import INITIAL_CONTROLLER_VALUE, ControllerTimeline

MODULATION: Final = 1
VOLUME: Final = 7
SUSTAIN: Final = 64

EVENTS: Final = (
    ControlChange(position=EventPosition(tick=0, sequence=0), channel=0, control=MODULATION, value=10),
    ControlChange(position=EventPosition(tick=0, sequence=1), channel=0, control=VOLUME, value=90),
    ControlChange(position=EventPosition(tick=240, sequence=4), channel=1, control=MODULATION, value=70),
    ControlChange(position=EventPosition(tick=480, sequence=7), channel=0, control=MODULATION, value=20),
    ControlChange(position=EventPosition(tick=480, sequence=8), channel=0, control=SUSTAIN, value=127),
    ControlChange(position=EventPosition(tick=960, sequence=11), channel=0, control=MODULATION, value=30),
)
TIMELINE: Final = ControllerTimeline(EVENTS)


def test_a_controller_nothing_was_posted_for_reads_as_the_value_a_receiver_starts_from() -> None:
    assert TIMELINE.value_before(0, 11, EventPosition(tick=960, sequence=20)) == INITIAL_CONTROLLER_VALUE
    assert TIMELINE.value_before(5, MODULATION, EventPosition(tick=960, sequence=20)) == INITIAL_CONTROLLER_VALUE


def test_a_controller_reads_the_last_value_posted_ahead_of_a_position() -> None:
    assert TIMELINE.value_before(0, MODULATION, EventPosition(tick=0, sequence=0)) == INITIAL_CONTROLLER_VALUE
    assert TIMELINE.value_before(0, MODULATION, EventPosition(tick=0, sequence=1)) == 10
    assert TIMELINE.value_before(0, MODULATION, EventPosition(tick=479, sequence=99)) == 10
    assert TIMELINE.value_before(0, MODULATION, EventPosition(tick=480, sequence=8)) == 20
    assert TIMELINE.value_before(0, MODULATION, EventPosition(tick=9999, sequence=0)) == 30


def test_the_value_at_a_position_is_read_from_the_message_ahead_of_it() -> None:
    """A note reads its opening settings at a position sorting ahead of everything on its tick."""
    onset = EventPosition.at_tick_start(480)

    assert TIMELINE.value_before(0, MODULATION, onset) == 10
    assert TIMELINE.value_before(0, SUSTAIN, onset) == INITIAL_CONTROLLER_VALUE


def test_the_messages_of_a_stretch_run_from_after_its_start_up_to_its_end() -> None:
    found = TIMELINE.events_between(
        frozenset({0}),
        EventPosition(tick=0, sequence=0),
        EventPosition(tick=480, sequence=7),
        frozenset(),
    )

    assert [(event.position.sequence, event.value) for event in found] == [(1, 90), (7, 20)]


def test_a_stretch_opening_at_a_tick_start_takes_in_the_messages_on_that_tick() -> None:
    found = TIMELINE.events_between(
        frozenset({0}),
        EventPosition.at_tick_start(0),
        EventPosition(tick=480, sequence=8),
        frozenset(),
    )

    assert [event.position.sequence for event in found] == [0, 1, 7, 8]


def test_the_named_controllers_are_left_out_of_a_stretch() -> None:
    found = TIMELINE.events_between(
        frozenset({0}),
        EventPosition.at_tick_start(0),
        EventPosition(tick=960, sequence=11),
        frozenset({SUSTAIN, VOLUME}),
    )

    assert [event.control for event in found] == [MODULATION, MODULATION, MODULATION]


def test_the_messages_of_several_channels_arrive_in_the_order_they_were_posted() -> None:
    found = TIMELINE.events_between(
        frozenset({1, 0}),
        EventPosition.at_tick_start(0),
        EventPosition(tick=480, sequence=8),
        frozenset(),
    )

    assert [event.position.sequence for event in found] == [0, 1, 4, 7, 8]
    assert [event.channel for event in found] == [0, 0, 1, 0, 0]


def test_a_channel_that_posted_nothing_contributes_nothing() -> None:
    found = TIMELINE.events_between(
        frozenset({9}),
        EventPosition.at_tick_start(0),
        EventPosition(tick=960, sequence=11),
        frozenset(),
    )

    assert not found


def test_one_controller_of_a_stretch_is_read_on_its_own() -> None:
    found = TIMELINE.control_events_between(
        0,
        MODULATION,
        EventPosition.at_tick_start(0),
        EventPosition(tick=960, sequence=11),
    )

    assert [event.value for event in found] == [10, 20, 30]


def test_a_controller_posted_nothing_over_a_stretch_reads_as_empty() -> None:
    found = TIMELINE.control_events_between(
        0,
        SUSTAIN,
        EventPosition.at_tick_start(0),
        EventPosition(tick=240, sequence=4),
    )

    assert not found
