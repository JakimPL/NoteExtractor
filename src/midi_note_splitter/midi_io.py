from pathlib import Path

from mido import MidiFile, merge_tracks

from .models import ControllerEvent, ParsedMidi, TimedMessage


def load_midi(path: Path) -> ParsedMidi:
    midi = MidiFile(path)
    if midi.ticks_per_beat <= 0:
        raise ValueError("SMPTE-timed MIDI files are not supported")

    tick = 0
    events: list[TimedMessage] = []
    controller_events: list[ControllerEvent] = []
    note_channels: set[int] = set()
    controller_channels: set[int] = set()

    for sequence, message in enumerate(merge_tracks(midi.tracks)):
        tick += message.time
        event = TimedMessage(
            tick=tick,
            sequence=sequence,
            message=message.copy(time=0),
        )
        events.append(event)

        if message.type in {"note_on", "note_off"}:
            note_channels.add(message.channel)
        elif message.type == "control_change":
            controller_channels.add(message.channel)
            controller_events.append(
                ControllerEvent(
                    tick=tick,
                    sequence=sequence,
                    channel=message.channel,
                    control=message.control,
                    value=message.value,
                )
            )

    end_sequence = len(events)
    return ParsedMidi(
        source_path=path,
        ticks_per_beat=midi.ticks_per_beat,
        events=tuple(events),
        controller_events=tuple(controller_events),
        end_tick=tick,
        end_sequence=end_sequence,
        note_channels=frozenset(note_channels),
        controller_channels=frozenset(controller_channels),
    )
