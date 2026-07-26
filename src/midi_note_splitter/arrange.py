from dataclasses import dataclass

from mido import Message, MetaMessage, MidiFile, MidiTrack, bpm2tempo

from .controllers import ControllerTimeline
from .models import MidiMessage, Note, RenderedNote
from .timing import TimeSignatureMap


@dataclass(frozen=True, slots=True)
class ArrangementConfig:
    bpm: float
    numerator: int
    denominator: int
    gap_measures: float
    tracked_ccs: frozenset[int]
    cc_channels: frozenset[int]
    sustain_pedal: bool


@dataclass(frozen=True, slots=True)
class ScheduledMessage:
    tick: int
    order: int
    serial: int
    message: MidiMessage


def arrange_notes(
    notes: list[Note],
    ticks_per_beat: int,
    controllers: ControllerTimeline,
    config: ArrangementConfig,
) -> tuple[MidiFile, list[RenderedNote]]:
    time_signatures = TimeSignatureMap.constant(
        ticks_per_beat,
        config.numerator,
        config.denominator,
    )
    gap_ticks = time_signatures.ticks_for_measures(config.gap_measures)
    sorted_notes = sorted(
        notes,
        key=lambda note: (
            note.pitch,
            note.velocity,
            note.start_tick,
            note.source_id,
        ),
    )

    scheduled: list[ScheduledMessage] = []
    rendered: list[RenderedNote] = []
    serial = 0
    cursor_tick = 0

    for render_index, note in enumerate(sorted_notes):
        key_duration = note.required_key_end_tick - note.start_tick
        release_duration = note.required_release_end_tick - note.start_tick
        render_note = RenderedNote(
            render_index=render_index,
            note=note,
            start_tick=cursor_tick,
            key_end_tick=cursor_tick + key_duration,
            release_end_tick=cursor_tick + release_duration,
        )
        rendered.append(render_note)

        serial = _schedule_note_segment(
            scheduled,
            serial,
            render_note,
            controllers,
            config,
        )
        cursor_tick = render_note.release_end_tick + gap_ticks

    midi = MidiFile(type=1, ticks_per_beat=ticks_per_beat)
    meta_track = MidiTrack()
    meta_track.append(MetaMessage("track_name", name="Timing", time=0))
    meta_track.append(MetaMessage("set_tempo", tempo=bpm2tempo(config.bpm), time=0))
    meta_track.append(
        MetaMessage(
            "time_signature",
            numerator=config.numerator,
            denominator=config.denominator,
            time=0,
        )
    )
    midi.tracks.append(meta_track)
    midi.tracks.append(_to_delta_track(scheduled))
    return midi, rendered


def _schedule_note_segment(
    scheduled: list[ScheduledMessage],
    serial: int,
    rendered: RenderedNote,
    controllers: ControllerTimeline,
    config: ArrangementConfig,
) -> int:
    note = rendered.note
    stream_channels = set(config.cc_channels)
    snapshot_pairs = {
        (channel, control)
        for channel in stream_channels
        for control in config.tracked_ccs
        if config.sustain_pedal or control != 64
    }
    if config.sustain_pedal:
        snapshot_pairs.add((note.channel, 64))

    snapshot_key = (note.start_tick, -1)
    snapshot_order = note.start_sequence - 1_000_000
    for channel, control in sorted(snapshot_pairs):
        value = controllers.value_before(channel, control, snapshot_key)
        serial = _append(
            scheduled,
            rendered.start_tick,
            snapshot_order,
            serial,
            Message(
                "control_change",
                channel=channel,
                control=control,
                value=value,
                time=0,
            ),
        )
        snapshot_order += 1

    serial = _append(
        scheduled,
        rendered.start_tick,
        note.start_sequence,
        serial,
        Message(
            "note_on",
            channel=note.channel,
            note=note.pitch,
            velocity=note.velocity,
            time=0,
        ),
    )

    copied_events = controllers.events_between(
        stream_channels,
        snapshot_key,
        note.release_end_key,
        set() if config.sustain_pedal else {64},
    )
    if config.sustain_pedal and note.channel not in stream_channels:
        copied_events.extend(
            event
            for event in controllers.events_between(
                {note.channel},
                snapshot_key,
                note.release_end_key,
            )
            if event.control == 64
        )
        copied_events.sort(key=lambda event: event.key)

    for event in copied_events:
        serial = _append(
            scheduled,
            rendered.start_tick + event.tick - note.start_tick,
            event.sequence,
            serial,
            Message(
                "control_change",
                channel=event.channel,
                control=event.control,
                value=event.value,
                time=0,
            ),
        )

    serial = _append(
        scheduled,
        rendered.key_end_tick,
        note.required_key_end_sequence,
        serial,
        Message(
            "note_off",
            channel=note.channel,
            note=note.pitch,
            velocity=note.release_velocity,
            time=0,
        ),
    )

    if config.sustain_pedal and rendered.release_end_tick > rendered.key_end_tick:
        serial = _append(
            scheduled,
            rendered.release_end_tick,
            note.required_release_end_sequence + 1_000_000,
            serial,
            Message(
                "control_change",
                channel=note.channel,
                control=64,
                value=0,
                time=0,
            ),
        )

    return serial


def _append(
    scheduled: list[ScheduledMessage],
    tick: int,
    order: int,
    serial: int,
    message: MidiMessage,
) -> int:
    scheduled.append(ScheduledMessage(tick, order, serial, message))
    return serial + 1


def _to_delta_track(scheduled: list[ScheduledMessage]) -> MidiTrack:
    track = MidiTrack()
    track.append(MetaMessage("track_name", name="Isolated notes", time=0))
    previous_tick = 0

    for item in sorted(
        scheduled,
        key=lambda value: (value.tick, value.order, value.serial),
    ):
        delta = item.tick - previous_tick
        track.append(item.message.copy(time=delta))
        previous_tick = item.tick

    return track
