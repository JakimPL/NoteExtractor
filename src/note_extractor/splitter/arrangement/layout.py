from collections.abc import Sequence
from typing import Final, Self

from pydantic import Field, model_validator

from ...errors import MidiSourceError
from ...models import FrozenModel
from ..notes import SourceNote
from .ordering import render_order

FIRST_RENDER_TICK: Final = 0


class RenderedNote(FrozenModel):
    """One source note placed on the render timeline under the index it was laid out at.

    The three ticks keep the spans the note sounds over, moved so that it starts at `start_tick`.
    """

    render_index: int = Field(ge=0)
    note: SourceNote
    start_tick: int = Field(ge=0)
    key_end_tick: int = Field(ge=0)
    release_end_tick: int = Field(ge=0)

    @model_validator(mode="after")
    def _require_ends_from_the_start_onwards(self) -> Self:
        if not self.start_tick <= self.key_end_tick <= self.release_end_tick:
            raise ValueError(
                f"render index {self.render_index} must end from its start onwards, stated as ticks "
                f"{self.start_tick} then {self.key_end_tick} then {self.release_end_tick}"
            )

        return self


def lay_out_notes(
    notes: Sequence[SourceNote],
    gap_ticks: int,
) -> tuple[RenderedNote, ...]:
    """Notes placed one after another along the render timeline, in render order.

    Every note keeps the spans it sounds over, and `gap_ticks` separates the release of one note
    from the onset of the next.

    Raises:
        MidiSourceError: If a note is let go of where it starts, which leaves the render no stretch
            to sound it over.
    """
    rendered: list[RenderedNote] = []
    start_tick = FIRST_RENDER_TICK
    for render_index, note in enumerate(sorted(notes, key=render_order)):
        placed = _placed(render_index, note, start_tick)
        rendered.append(placed)
        start_tick = placed.release_end_tick + gap_ticks

    return tuple(rendered)


def _placed(
    render_index: int,
    note: SourceNote,
    start_tick: int,
) -> RenderedNote:
    """One note placed at the given tick of the render, keeping the spans it sounds over.

    Raises:
        MidiSourceError: If the note is let go of where it starts.
    """
    if note.release_duration_ticks <= 0:
        raise MidiSourceError(
            f"note {note.source_id} sounds over no ticks: pitch {note.pitch} at tick "
            f"{note.start.tick} is let go of where it starts"
        )

    return RenderedNote(
        render_index=render_index,
        note=note,
        start_tick=start_tick,
        key_end_tick=start_tick + note.key_duration_ticks,
        release_end_tick=start_tick + note.release_duration_ticks,
    )
