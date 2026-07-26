from bisect import bisect_left, bisect_right

from note_extractor.midi.events import EventPosition


def test_positions_sort_by_tick_then_sequence() -> None:
    positions = [
        EventPosition(tick=1, sequence=5),
        EventPosition(tick=0, sequence=9),
        EventPosition(tick=1, sequence=2),
    ]

    assert sorted(positions) == [
        EventPosition(tick=0, sequence=9),
        EventPosition(tick=1, sequence=2),
        EventPosition(tick=1, sequence=5),
    ]


def test_tick_start_sorts_ahead_of_every_event_on_that_tick() -> None:
    assert EventPosition.at_tick_start(4) < EventPosition(tick=4, sequence=0)
    assert EventPosition.at_tick_start(4) > EventPosition(tick=3, sequence=1_000)


def test_positions_serve_as_bisect_keys() -> None:
    positions = [
        EventPosition(tick=0, sequence=0),
        EventPosition(tick=4, sequence=1),
        EventPosition(tick=4, sequence=7),
    ]

    assert bisect_left(positions, EventPosition.at_tick_start(4)) == 1
    assert bisect_right(positions, EventPosition(tick=4, sequence=7)) == 3
