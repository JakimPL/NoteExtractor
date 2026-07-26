from collections.abc import Sequence
from typing import Final, Self

from pydantic import Field

from ..manifest.models import NoteRecord
from ..models import FrozenModel
from .config import MAX_CC_DECIMALS, MIN_CC_DECIMALS

MIN_INDEX_WIDTH: Final = 4
FIRST_RENDER_INDEX: Final = 0

FIELD_SEPARATOR: Final = "_"
SAMPLE_SUFFIX: Final = ".wav"
DECIMAL_POINT_MARKER: Final = "p"
MINUS_SIGN_MARKER: Final = "m"


class SampleNaming(FrozenModel):
    """Names the sample files of one run so each states which note it holds.

    A name opens with the render index, carries the pitch and the velocity the note was played with,
    and ends with the average of every controller the split tracked. Every index is written to
    `index_width` digits, so the names of one run sort in the order the render sounds them.
    """

    index_width: int = Field(ge=MIN_INDEX_WIDTH)
    cc_decimals: int = Field(ge=MIN_CC_DECIMALS, le=MAX_CC_DECIMALS)

    @classmethod
    def for_notes(cls, notes: Sequence[NoteRecord], cc_decimals: int) -> Self:
        """Naming wide enough to write the highest render index the given notes were laid out at."""
        highest = max((note.render.index for note in notes), default=FIRST_RENDER_INDEX)
        return cls(index_width=max(MIN_INDEX_WIDTH, len(str(highest))), cc_decimals=cc_decimals)

    def filename_for(self, note: NoteRecord) -> str:
        """Name of the file holding one note's sample."""
        parts = [
            f"{note.render.index:0{self.index_width}d}",
            f"p{note.pitch:03d}",
            f"v{note.velocity:03d}",
        ]
        parts.extend(f"cc{control}-{self._written(note.cc_averages[control])}" for control in sorted(note.cc_averages))
        return FIELD_SEPARATOR.join(parts) + SAMPLE_SUFFIX

    def _written(self, average: float) -> str:
        """One controller average as a file name states it.

        A run keeping decimals writes the value to `cc_decimals` places and trims the trailing zeros,
        so a whole number reads as `64`; a run keeping none writes the value rounded to a whole
        number, where the trailing zeros of `100` state its size. The decimal point reads as `p` and
        a minus sign as `m`, which keeps a name to characters every filesystem accepts.
        """
        text = f"{average:.{self.cc_decimals}f}"
        if self.cc_decimals:
            text = text.rstrip("0").rstrip(".")

        return text.replace("-", MINUS_SIGN_MARKER).replace(".", DECIMAL_POINT_MARKER)
