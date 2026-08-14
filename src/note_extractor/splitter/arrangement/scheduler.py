import itertools
from collections.abc import Sequence

from ...midi.constants import PEDAL_DOWN_THRESHOLD, PEDAL_UP_VALUE, SUSTAIN_PEDAL_CONTROL
from ...midi.events import (
    ControlChange,
    EventPosition,
    NoteOff,
    NoteOn,
    PerformanceEvent,
)
from ..config import RenderSettings
from ..controllers import ControllerTimeline
from ..notes import SourceNote
from .layout import RenderedNote
from .ordering import OrderBand, ScheduledMessage


class NoteScheduler:
    """Voices each rendered note and places its messages into one write order for the render.

    A note opens with a snapshot of the controllers the run tracks, so it sounds with the settings
    the source held at its onset, and carries the controller messages the source posted while it
    sounded. A run following the sustain pedal closes a note the pedal is still holding where it
    ends by letting the pedal up. One scheduler places one render.
    """

    def __init__(self, controllers: ControllerTimeline, settings: RenderSettings) -> None:
        self._controllers = controllers
        self._settings = settings
        self._serials = itertools.count()
        self._messages: list[ScheduledMessage] = []

    def schedule(self, rendered_notes: Sequence[RenderedNote]) -> tuple[PerformanceEvent, ...]:
        """Events voicing the given notes, in the order they are written to the render."""
        for rendered in rendered_notes:
            self._place(rendered)

        return tuple(message.event for message in sorted(self._messages))

    def _place(self, rendered: RenderedNote) -> None:
        """Voice one note, from the settings it opens with to the pedal release closing it."""
        self._emit_snapshot(rendered)
        self._emit_key_press(rendered)
        self._emit_copied_controllers(rendered)
        self._emit_key_release(rendered)
        self._emit_pedal_release(rendered)

    def _emit_snapshot(self, rendered: RenderedNote) -> None:
        """Post the value each tracked controller held at the note's onset."""
        note = rendered.note
        onset = EventPosition.at_tick_start(note.start.tick)
        for channel, control in self._snapshot_pairs(note.channel):
            self._emit(
                ControlChange(
                    position=EventPosition(tick=rendered.start_tick, sequence=note.start.sequence),
                    channel=channel,
                    control=control,
                    value=self._controllers.value_before(channel, control, onset),
                ),
                OrderBand.SNAPSHOT,
            )

    def _emit_key_press(self, rendered: RenderedNote) -> None:
        """Strike the key with the velocity it was played at."""
        note = rendered.note
        self._emit(
            NoteOn(
                position=EventPosition(tick=rendered.start_tick, sequence=note.start.sequence),
                channel=note.channel,
                pitch=note.pitch,
                velocity=note.velocity,
            ),
            OrderBand.SOURCE,
        )

    def _emit_copied_controllers(self, rendered: RenderedNote) -> None:
        """Copy the controller messages the source posted while the note sounded."""
        note = rendered.note
        shift = rendered.start_tick - note.start.tick
        for event in self._copied_events(note):
            self._emit(
                ControlChange(
                    position=EventPosition(tick=event.position.tick + shift, sequence=event.position.sequence),
                    channel=event.channel,
                    control=event.control,
                    value=event.value,
                ),
                OrderBand.SOURCE,
            )

    def _emit_key_release(self, rendered: RenderedNote) -> None:
        """Release the key with the velocity it was released at."""
        note = rendered.note
        self._emit(
            NoteOff(
                position=EventPosition(tick=rendered.key_end_tick, sequence=note.key_end.sequence),
                channel=note.channel,
                pitch=note.pitch,
                velocity=note.release_velocity,
            ),
            OrderBand.SOURCE,
        )

    def _emit_pedal_release(self, rendered: RenderedNote) -> None:
        """Let the sustain pedal up for a note the pedal is still holding where it is let go of."""
        note = rendered.note
        if not self._settings.sustain_pedal or not self._pedal_holds_at_the_end_of(note):
            return

        self._emit(
            ControlChange(
                position=EventPosition(tick=rendered.release_end_tick, sequence=note.release_end.sequence),
                channel=note.channel,
                control=SUSTAIN_PEDAL_CONTROL,
                value=PEDAL_UP_VALUE,
            ),
            OrderBand.PEDAL_LIFT,
        )

    def _pedal_holds_at_the_end_of(self, note: SourceNote) -> bool:
        """Whether the pedal the render carries is down where the note is let go of.

        The render opens each note with the pedal its source stretch held and copies the messages
        moving it from there on, so the value the source held ahead of that moment is the value the
        render holds there too. A note the run itself lets go of — one held on to the shortest span
        it sounds, one cut short at the longest — comes to rest on a key release alone, and lifting
        the pedal there is what keeps its sound out of the notes laid out after it.
        """
        held = self._controllers.value_before(note.channel, SUSTAIN_PEDAL_CONTROL, note.release_end)
        return held >= PEDAL_DOWN_THRESHOLD

    def _emit(self, event: PerformanceEvent, band: OrderBand) -> None:
        """Take in one voiced event, ranked within its tick by band and by emission order."""
        self._messages.append(ScheduledMessage.for_event(event, band, next(self._serials)))

    def _snapshot_pairs(self, note_channel: int) -> tuple[tuple[int, int], ...]:
        """Channel and controller pairs a note opens with, in ascending order.

        A run following the sustain pedal states the pedal on the note's own channel, which is how a
        note played on a channel outside the copied ones still opens with its pedal settled.
        """
        pairs = {
            (channel, control) for channel in self._settings.cc_channels for control in self._settings.applied_controls
        }
        if self._settings.sustain_pedal:
            pairs.add((note_channel, SUSTAIN_PEDAL_CONTROL))

        return tuple(sorted(pairs))

    def _copied_events(self, note: SourceNote) -> tuple[ControlChange, ...]:
        """Controller messages of the note's stretch, in the order the source posted them."""
        onset = EventPosition.at_tick_start(note.start.tick)
        ignored: frozenset[int] = frozenset() if self._settings.sustain_pedal else frozenset({SUSTAIN_PEDAL_CONTROL})
        copied = self._controllers.events_between(self._settings.cc_channels, onset, note.release_end, ignored)
        if not self._settings.sustain_pedal or note.channel in self._settings.cc_channels:
            return copied

        pedal = self._controllers.control_events_between(
            note.channel,
            SUSTAIN_PEDAL_CONTROL,
            onset,
            note.release_end,
        )
        return tuple(sorted(copied + pedal, key=lambda event: event.position))
