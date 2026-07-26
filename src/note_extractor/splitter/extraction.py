from collections import deque

from ..midi.constants import PEDAL_DOWN_THRESHOLD, SUSTAIN_PEDAL_CONTROL
from ..midi.events import ControlChange, EventPosition, MidiEvent, NoteOff, NoteOn
from ..midi.source import SourceMidi
from .notes import NoteDraft


class SustainPedalState:
    """Sustain pedal position on each channel of one performance."""

    def __init__(self) -> None:
        self._down_channels: set[int] = set()

    def is_down(self, channel: int) -> bool:
        """Whether the pedal on the given channel is held down."""
        return channel in self._down_channels

    def take(self, event: ControlChange) -> bool:
        """Take in one pedal message, reporting whether it let a held pedal up."""
        was_down = self.is_down(event.channel)
        if event.value >= PEDAL_DOWN_THRESHOLD:
            self._down_channels.add(event.channel)
            return False

        self._down_channels.discard(event.channel)
        return was_down


class NoteExtractor:
    """Reads the notes of one performance, following the sustain pedal when a run asks for it.

    A note sounds from its key press until its sound is let go: at the key release while the pedal
    is up, at the pedal release for a key released while the pedal is down, and at the end of the
    performance for a note still sounding when the stream runs out. Repeated presses of one key
    pair up with the releases of that key in the order they arrive. One extractor reads one
    performance.
    """

    def __init__(self, sustain_pedal: bool) -> None:
        self._sustain_pedal = sustain_pedal
        self._pedal = SustainPedalState()
        self._sounding: dict[tuple[int, int], deque[NoteDraft]] = {}
        self._sustained: dict[int, list[NoteDraft]] = {}
        self._drafts: list[NoteDraft] = []

    def extract(self, source: SourceMidi) -> tuple[NoteDraft, ...]:
        """Notes of one performance, in the order their keys were pressed."""
        for event in source.events:
            self._take(event)

        self._close_at(source.end_position)
        return tuple(self._drafts)

    def _take(self, event: MidiEvent) -> None:
        """Follow one event through to the notes it starts, ends, or lets go of."""
        if isinstance(event, NoteOn):
            self._press(event)
        elif isinstance(event, NoteOff):
            self._release(event)
        elif isinstance(event, ControlChange) and self._is_pedal(event):
            self._move_pedal(event)

    def _is_pedal(self, event: ControlChange) -> bool:
        """Whether one controller message moves a pedal this run follows."""
        return self._sustain_pedal and event.control == SUSTAIN_PEDAL_CONTROL

    def _press(self, event: NoteOn) -> None:
        """Start a note on the pressed key."""
        draft = NoteDraft(
            source_id=len(self._drafts),
            channel=event.channel,
            pitch=event.pitch,
            velocity=event.velocity,
            start=event.position,
        )
        self._drafts.append(draft)
        self._sounding.setdefault((event.channel, event.pitch), deque()).append(draft)

    def _release(self, event: NoteOff) -> None:
        """End the note the released key started, holding its sound while the pedal is down."""
        sounding = self._sounding.get((event.channel, event.pitch))
        if not sounding:
            return

        draft = sounding.popleft()
        draft.key_end = event.position
        draft.release_velocity = event.velocity
        if self._pedal.is_down(event.channel):
            self._sustained.setdefault(event.channel, []).append(draft)
        else:
            draft.release_end = event.position

    def _move_pedal(self, event: ControlChange) -> None:
        """Take in one pedal message, letting go of the notes its release frees."""
        if self._pedal.take(event):
            for draft in self._sustained.pop(event.channel, []):
                draft.release_end = event.position

    def _close_at(self, position: EventPosition) -> None:
        """Let go of every note still sounding where the performance runs out."""
        for sounding in self._sounding.values():
            for draft in sounding:
                draft.key_end = position
                draft.release_end = position

        for drafts in self._sustained.values():
            for draft in drafts:
                draft.release_end = position
