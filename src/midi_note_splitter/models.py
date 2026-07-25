from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from mido import Message, MetaMessage

MidiMessage = Message | MetaMessage


@dataclass(frozen=True, slots=True)
class TimedMessage:
    tick: int
    sequence: int
    message: MidiMessage


@dataclass(frozen=True, slots=True)
class ControllerEvent:
    tick: int
    sequence: int
    channel: int
    control: int
    value: int

    @property
    def key(self) -> tuple[int, int]:
        return self.tick, self.sequence


@dataclass(slots=True)
class Note:
    source_id: int
    channel: int
    pitch: int
    velocity: int
    start_tick: int
    start_sequence: int
    key_end_tick: int | None = None
    key_end_sequence: int | None = None
    release_end_tick: int | None = None
    release_end_sequence: int | None = None
    release_velocity: int = 0
    cc_averages: dict[int, float] = field(default_factory=dict)

    @property
    def start_key(self) -> tuple[int, int]:
        return self.start_tick, self.start_sequence

    @property
    def key_end_key(self) -> tuple[int, int]:
        return self.required_key_end_tick, self.required_key_end_sequence

    @property
    def release_end_key(self) -> tuple[int, int]:
        return self.required_release_end_tick, self.required_release_end_sequence

    @property
    def required_key_end_tick(self) -> int:
        if self.key_end_tick is None:
            raise ValueError("note has no key end")
        return self.key_end_tick

    @property
    def required_key_end_sequence(self) -> int:
        if self.key_end_sequence is None:
            raise ValueError("note has no key end sequence")
        return self.key_end_sequence

    @property
    def required_release_end_tick(self) -> int:
        if self.release_end_tick is None:
            raise ValueError("note has no release end")
        return self.release_end_tick

    @property
    def required_release_end_sequence(self) -> int:
        if self.release_end_sequence is None:
            raise ValueError("note has no release end sequence")
        return self.release_end_sequence


@dataclass(frozen=True, slots=True)
class RenderedNote:
    render_index: int
    note: Note
    start_tick: int
    key_end_tick: int
    release_end_tick: int


@dataclass(frozen=True, slots=True)
class ParsedMidi:
    source_path: Path
    ticks_per_beat: int
    events: tuple[TimedMessage, ...]
    controller_events: tuple[ControllerEvent, ...]
    end_tick: int
    end_sequence: int
    note_channels: frozenset[int]
    controller_channels: frozenset[int]
