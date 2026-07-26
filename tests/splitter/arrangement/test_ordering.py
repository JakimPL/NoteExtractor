from note_extractor.midi.events import ControlChange, EventPosition, NoteOn
from note_extractor.splitter.arrangement.ordering import OrderBand, ScheduledMessage, render_order
from note_extractor.splitter.notes import SourceNote


def test_a_snapshot_leads_its_tick_and_a_pedal_release_closes_it() -> None:
    assert OrderBand.SNAPSHOT < OrderBand.SOURCE < OrderBand.PEDAL_LIFT


def test_a_message_takes_the_render_position_its_event_carries() -> None:
    event = _note_on(tick=960, sequence=7)

    message = ScheduledMessage.for_event(event, OrderBand.SOURCE, serial=3)

    assert (message.tick, message.band, message.sequence, message.serial) == (960, OrderBand.SOURCE, 7, 3)
    assert message.event is event


def test_the_earlier_tick_is_written_first() -> None:
    early = ScheduledMessage.for_event(_note_on(tick=0, sequence=99), OrderBand.PEDAL_LIFT, serial=9)
    late = ScheduledMessage.for_event(_note_on(tick=1, sequence=0), OrderBand.SNAPSHOT, serial=0)

    assert sorted([late, early]) == [early, late]


def test_within_one_tick_the_band_settles_the_order() -> None:
    snapshot = ScheduledMessage.for_event(_control(tick=480, sequence=50), OrderBand.SNAPSHOT, serial=8)
    source = ScheduledMessage.for_event(_note_on(tick=480, sequence=10), OrderBand.SOURCE, serial=1)
    pedal = ScheduledMessage.for_event(_control(tick=480, sequence=2), OrderBand.PEDAL_LIFT, serial=0)

    assert sorted([pedal, source, snapshot]) == [snapshot, source, pedal]


def test_within_one_band_the_order_the_source_posted_them_in_settles_it() -> None:
    first = ScheduledMessage.for_event(_control(tick=480, sequence=3), OrderBand.SOURCE, serial=7)
    second = ScheduledMessage.for_event(_note_on(tick=480, sequence=4), OrderBand.SOURCE, serial=2)

    assert sorted([second, first]) == [first, second]


def test_messages_the_source_placed_alike_keep_the_order_they_were_emitted_in() -> None:
    first = ScheduledMessage.for_event(_control(tick=0, sequence=5), OrderBand.SNAPSHOT, serial=0)
    second = ScheduledMessage.for_event(_control(tick=0, sequence=5), OrderBand.SNAPSHOT, serial=1)

    assert sorted([second, first]) == [first, second]


def test_notes_are_laid_out_by_pitch_then_strike_then_when_they_were_played() -> None:
    quiet_high = _note(source_id=0, pitch=72, velocity=40, start_tick=0)
    loud_low = _note(source_id=1, pitch=60, velocity=100, start_tick=960)
    quiet_low = _note(source_id=2, pitch=60, velocity=40, start_tick=1920)
    repeat = _note(source_id=3, pitch=60, velocity=100, start_tick=0)

    laid_out = sorted([quiet_high, loud_low, quiet_low, repeat], key=render_order)

    assert [note.source_id for note in laid_out] == [2, 3, 1, 0]


def test_two_notes_alike_in_every_way_are_laid_out_by_the_order_they_were_read() -> None:
    first = _note(source_id=4, pitch=60, velocity=100, start_tick=480)
    second = _note(source_id=2, pitch=60, velocity=100, start_tick=480)

    assert [note.source_id for note in sorted([first, second], key=render_order)] == [2, 4]


def _note_on(tick: int, sequence: int) -> NoteOn:
    return NoteOn(position=EventPosition(tick=tick, sequence=sequence), channel=0, pitch=60, velocity=100)


def _control(tick: int, sequence: int) -> ControlChange:
    return ControlChange(position=EventPosition(tick=tick, sequence=sequence), channel=0, control=1, value=0)


def _note(source_id: int, pitch: int, velocity: int, start_tick: int) -> SourceNote:
    return SourceNote(
        source_id=source_id,
        channel=0,
        pitch=pitch,
        velocity=velocity,
        release_velocity=0,
        start=EventPosition(tick=start_tick, sequence=0),
        key_end=EventPosition(tick=start_tick + 480, sequence=1),
        release_end=EventPosition(tick=start_tick + 480, sequence=1),
    )
