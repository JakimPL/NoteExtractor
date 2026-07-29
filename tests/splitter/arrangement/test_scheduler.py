from collections.abc import Sequence
from typing import Final

from note_extractor.midi.events import ControlChange, EventPosition, NoteOn, PerformanceEvent
from note_extractor.splitter.arrangement.layout import lay_out_notes
from note_extractor.splitter.arrangement.scheduler import NoteScheduler
from note_extractor.splitter.config import RenderSettings, SplitConfig
from note_extractor.splitter.controllers import ControllerTimeline
from note_extractor.splitter.notes import SourceNote

from ..conftest import split_config

TICKS_PER_BEAT: Final = 480
MODULATION: Final = 1
VOLUME: Final = 7
SUSTAIN: Final = 64


def test_a_note_opens_with_the_settings_its_source_stretch_held() -> None:
    controllers = ControllerTimeline(
        [
            _posted(tick=0, sequence=0, channel=0, control=MODULATION, value=90),
            _posted(tick=0, sequence=1, channel=0, control=VOLUME, value=100),
        ],
    )
    settings = _settings(split_config(tracked_ccs=frozenset({MODULATION, VOLUME}), sustain_pedal=False))

    events = _schedule(controllers, settings, [_note(start_tick=480, key_end_tick=960, release_end_tick=960)])

    assert _voiced(events[:2]) == [("control_change", MODULATION, 90), ("control_change", VOLUME, 100)]
    assert isinstance(events[2], NoteOn)


def test_a_controller_on_the_onset_tick_keeps_its_place_around_the_key_press() -> None:
    """A sequencer's own order at the onset tick decides which values the strike hears."""
    controllers = ControllerTimeline(
        [
            _posted(tick=0, sequence=0, channel=0, control=VOLUME, value=90),
            _posted(tick=0, sequence=2, channel=0, control=MODULATION, value=20),
        ],
    )
    settings = _settings(split_config(tracked_ccs=frozenset({MODULATION}), sustain_pedal=False))
    note = _note(start_tick=0, key_end_tick=480, release_end_tick=480, start_sequence=1)

    events = _schedule(controllers, settings, [note])

    assert _voiced(events) == [
        ("control_change", MODULATION, 0),
        ("control_change", VOLUME, 90),
        ("note_on", 60, 100),
        ("control_change", MODULATION, 20),
        ("note_off", 60, 0),
    ]


def test_the_controllers_of_a_note_stretch_are_copied_where_the_note_was_laid_out() -> None:
    controllers = ControllerTimeline(
        [
            _posted(tick=1200, sequence=5, channel=0, control=MODULATION, value=30),
            _posted(tick=1440, sequence=6, channel=0, control=MODULATION, value=60),
        ],
    )
    settings = _settings(split_config(tracked_ccs=frozenset({MODULATION}), sustain_pedal=False))
    note = _note(start_tick=960, key_end_tick=1920, release_end_tick=1920, start_sequence=1)

    events = _schedule(controllers, settings, [note])

    assert [(event.position.tick, _value(event)) for event in events] == [
        (0, 0),
        (0, 100),
        (240, 30),
        (480, 60),
        (960, 0),
    ]


def test_a_controller_posted_after_the_note_was_let_go_of_stays_out_of_the_render() -> None:
    controllers = ControllerTimeline(
        [_posted(tick=1921, sequence=9, channel=0, control=MODULATION, value=60)],
    )
    settings = _settings(split_config(tracked_ccs=frozenset({MODULATION}), sustain_pedal=False))
    note = _note(start_tick=960, key_end_tick=1920, release_end_tick=1920, start_sequence=1)

    events = _schedule(controllers, settings, [note])

    assert [_value(event) for event in events] == [0, 100, 0]


def test_a_note_sounding_past_its_key_release_closes_with_the_pedal_coming_up() -> None:
    controllers = ControllerTimeline(
        [_posted(tick=0, sequence=0, channel=0, control=SUSTAIN, value=127)],
    )
    settings = _settings(split_config(tracked_ccs=frozenset({SUSTAIN}), sustain_pedal=True))
    note = _note(start_tick=480, key_end_tick=960, release_end_tick=1200, start_sequence=1)

    events = _schedule(controllers, settings, [note])

    assert _voiced(events) == [
        ("control_change", SUSTAIN, 127),
        ("note_on", 60, 100),
        ("note_off", 60, 0),
        ("control_change", SUSTAIN, 0),
    ]
    assert [event.position.tick for event in events] == [0, 0, 480, 720]


def test_a_note_let_go_of_at_its_key_release_needs_no_pedal_release() -> None:
    controllers = ControllerTimeline([])
    settings = _settings(split_config(tracked_ccs=frozenset({SUSTAIN}), sustain_pedal=True))
    note = _note(start_tick=0, key_end_tick=480, release_end_tick=480, start_sequence=1)

    events = _schedule(controllers, settings, [note])

    assert _voiced(events) == [
        ("control_change", SUSTAIN, 0),
        ("note_on", 60, 100),
        ("note_off", 60, 0),
    ]


def test_a_run_leaving_the_pedal_alone_keeps_it_out_of_the_render() -> None:
    controllers = ControllerTimeline(
        [
            _posted(tick=0, sequence=0, channel=0, control=SUSTAIN, value=127),
            _posted(tick=240, sequence=3, channel=0, control=SUSTAIN, value=0),
        ],
    )
    settings = _settings(split_config(tracked_ccs=frozenset({MODULATION, SUSTAIN}), sustain_pedal=False))
    note = _note(start_tick=0, key_end_tick=480, release_end_tick=480, start_sequence=1)

    events = _schedule(controllers, settings, [note])

    assert [event for event in events if _control_of(event) == SUSTAIN] == []


def test_a_note_played_outside_the_copied_channels_still_opens_with_its_own_pedal() -> None:
    """A performance may carry its notes on one channel and the controllers the render copies on another."""
    controllers = ControllerTimeline(
        [
            _posted(tick=0, sequence=0, channel=0, control=MODULATION, value=55),
            _posted(tick=0, sequence=1, channel=3, control=SUSTAIN, value=127),
        ],
    )
    settings = _settings(
        split_config(tracked_ccs=frozenset({MODULATION}), cc_channels=frozenset({0}), sustain_pedal=True)
    )
    note = _note(start_tick=240, key_end_tick=720, release_end_tick=840, channel=3, start_sequence=2)

    events = _schedule(controllers, settings, [note])

    assert _voiced(events) == [
        ("control_change", MODULATION, 55),
        ("control_change", SUSTAIN, 127),
        ("note_on", 60, 100),
        ("note_off", 60, 0),
        ("control_change", SUSTAIN, 0),
    ]
    assert [event.channel for event in events] == [0, 3, 3, 3, 3]
    assert [event.position.tick for event in events] == [0, 0, 0, 480, 600]


def test_every_note_of_a_render_is_voiced_in_the_order_it_was_laid_out() -> None:
    controllers = ControllerTimeline([])
    settings = _settings(split_config(tracked_ccs=frozenset({MODULATION}), sustain_pedal=False))
    notes = [
        _note(start_tick=0, key_end_tick=480, release_end_tick=480, pitch=72, start_sequence=1),
        _note(start_tick=960, key_end_tick=1440, release_end_tick=1440, pitch=60, start_sequence=4),
    ]

    rendered = lay_out_notes(notes, gap_ticks=480)
    events = NoteScheduler(controllers, settings).schedule(rendered)

    assert [(event.position.tick, _voiced_pitch(event)) for event in events] == [
        (0, None),
        (0, 60),
        (480, 60),
        (960, None),
        (960, 72),
        (1440, 72),
    ]


def _settings(config: SplitConfig) -> RenderSettings:
    return RenderSettings.from_config(config, TICKS_PER_BEAT, frozenset({0}))


def _schedule(
    controllers: ControllerTimeline,
    settings: RenderSettings,
    notes: Sequence[SourceNote],
) -> tuple[PerformanceEvent, ...]:
    return NoteScheduler(controllers, settings).schedule(lay_out_notes(notes, settings.gap_ticks))


def _posted(tick: int, sequence: int, channel: int, control: int, value: int) -> ControlChange:
    return ControlChange(
        position=EventPosition(tick=tick, sequence=sequence),
        channel=channel,
        control=control,
        value=value,
    )


def _note(
    start_tick: int,
    key_end_tick: int,
    release_end_tick: int,
    pitch: int = 60,
    channel: int = 0,
    start_sequence: int = 1,
) -> SourceNote:
    return SourceNote(
        source_id=0,
        channel=channel,
        pitch=pitch,
        velocity=100,
        release_velocity=0,
        start=EventPosition(tick=start_tick, sequence=start_sequence),
        key_end=EventPosition(tick=key_end_tick, sequence=start_sequence + 10),
        release_end=EventPosition(tick=release_end_tick, sequence=start_sequence + 20),
    )


def _voiced(events: Sequence[PerformanceEvent]) -> list[tuple[str, int, int]]:
    """Each event as its kind, the pitch or controller it names, and the value it carries."""
    return [
        (
            _kind(event),
            event.control if isinstance(event, ControlChange) else event.pitch,
            event.value if isinstance(event, ControlChange) else event.velocity,
        )
        for event in events
    ]


def _kind(event: PerformanceEvent) -> str:
    if isinstance(event, ControlChange):
        return "control_change"

    return "note_on" if isinstance(event, NoteOn) else "note_off"


def _value(event: PerformanceEvent) -> int:
    return event.value if isinstance(event, ControlChange) else event.velocity


def _control_of(event: PerformanceEvent) -> int | None:
    return event.control if isinstance(event, ControlChange) else None


def _voiced_pitch(event: PerformanceEvent) -> int | None:
    return None if isinstance(event, ControlChange) else event.pitch
