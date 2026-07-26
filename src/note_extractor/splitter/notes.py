from dataclasses import dataclass
from typing import Final, Self

from pydantic import Field, model_validator

from ..midi.constants import DataByte, MidiChannel
from ..midi.events import EventPosition
from ..models import FrozenModel

INITIAL_RELEASE_VELOCITY: Final = 0


@dataclass(slots=True)
class NoteDraft:
    """One note taking shape while its performance is read.

    The ends arrive after the start, so they stand open until the stream supplies them: a key
    release settles `key_end`, and the moment the sound is let go settles `release_end`, which the
    sustain pedal holds past the key release. `finalize` turns a draft whose ends have arrived into
    the note it settled on.
    """

    source_id: int
    channel: int
    pitch: int
    velocity: int
    start: EventPosition
    key_end: EventPosition | None = None
    release_end: EventPosition | None = None
    release_velocity: int = INITIAL_RELEASE_VELOCITY


class SourceNote(FrozenModel):
    """One note as it was played, bounded by the three moments that place it in the performance.

    The key end marks the release of the key; the release end marks the moment the sound was let
    go, which the sustain pedal holds past the key end. `source_id` orders the notes by the order
    their keys were pressed.
    """

    source_id: int = Field(ge=0)
    channel: MidiChannel
    pitch: DataByte
    velocity: DataByte
    release_velocity: DataByte
    start: EventPosition
    key_end: EventPosition
    release_end: EventPosition

    @model_validator(mode="after")
    def _require_ends_from_the_start_onwards(self) -> Self:
        if not self.start <= self.key_end <= self.release_end:
            raise ValueError(
                f"note {self.source_id} must end from its start onwards, stated as "
                f"{self.start} then {self.key_end} then {self.release_end}"
            )

        return self

    @property
    def key_duration_ticks(self) -> int:
        """Ticks the key was held down for."""
        return self.key_end.tick - self.start.tick

    @property
    def release_duration_ticks(self) -> int:
        """Ticks the note sounded for, up to the moment its sound was let go."""
        return self.release_end.tick - self.start.tick


def finalize(draft: NoteDraft) -> SourceNote:
    """The note one draft settled on, once its performance has been read to the end.

    Raises:
        ValueError: If the draft stands open at its key end or at its release end.
    """
    if draft.key_end is None or draft.release_end is None:
        raise ValueError(f"note {draft.source_id} stands open at tick {draft.start.tick}")

    return SourceNote(
        source_id=draft.source_id,
        channel=draft.channel,
        pitch=draft.pitch,
        velocity=draft.velocity,
        release_velocity=draft.release_velocity,
        start=draft.start,
        key_end=draft.key_end,
        release_end=draft.release_end,
    )
