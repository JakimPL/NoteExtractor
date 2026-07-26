from collections.abc import Sequence

from ...midi.score import RenderScore
from ..config import RenderSettings
from ..controllers import ControllerTimeline
from ..notes import SourceNote
from .layout import RenderedNote, lay_out_notes
from .scheduler import NoteScheduler


def arrange_notes(
    notes: Sequence[SourceNote],
    controllers: ControllerTimeline,
    settings: RenderSettings,
) -> tuple[RenderScore, tuple[RenderedNote, ...]]:
    """One note at a time score of the given notes, together with where each was laid out.

    Notes are laid out along the render timeline in render order, voiced with the controller
    settings their source stretch held, and written into a score carrying the render's own tempo
    and time signature.
    """
    rendered_notes = lay_out_notes(notes, settings.gap_ticks)
    return (
        RenderScore(
            ticks_per_beat=settings.ticks_per_beat,
            microseconds_per_beat=settings.microseconds_per_beat,
            numerator=settings.signature.numerator,
            denominator=settings.signature.denominator,
            events=NoteScheduler(controllers, settings).schedule(rendered_notes),
        ),
        rendered_notes,
    )
