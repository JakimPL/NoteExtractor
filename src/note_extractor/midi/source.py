from dataclasses import dataclass

from .events import (
    ControlChange,
    EventPosition,
    MeterChange,
    MidiEvent,
    NoteOff,
    NoteOn,
    TempoChange,
)


@dataclass(frozen=True, slots=True)
class SourceMidi:
    """One MIDI performance as typed events, each positioned in the merged message stream.

    `end_position` marks the end of the performance and serves as the release point for notes
    still sounding when the stream runs out. The view methods narrow `events` for the consumers
    that work with a single event kind.
    """

    ticks_per_beat: int
    events: tuple[MidiEvent, ...]
    end_position: EventPosition

    def control_changes(self) -> tuple[ControlChange, ...]:
        """Controller events in stream order."""
        return tuple(event for event in self.events if isinstance(event, ControlChange))

    def tempo_changes(self) -> tuple[TempoChange, ...]:
        """Tempo changes in stream order."""
        return tuple(event for event in self.events if isinstance(event, TempoChange))

    def meter_changes(self) -> tuple[MeterChange, ...]:
        """Time signature changes in stream order."""
        return tuple(event for event in self.events if isinstance(event, MeterChange))

    def note_channels(self) -> frozenset[int]:
        """Channels carrying at least one key press or key release."""
        return frozenset(event.channel for event in self.events if isinstance(event, NoteOn | NoteOff))
