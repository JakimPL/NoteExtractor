from __future__ import annotations

from .models import ManifestNote


def sample_filename(note: ManifestNote, cc_decimals: int, index_width: int) -> str:
    parts = [
        f"{note.render_index:0{index_width}d}",
        f"p{note.pitch:03d}",
        f"v{note.velocity:03d}",
    ]
    parts.extend(
        f"cc{control}-{_format_value(value, cc_decimals)}" for control, value in sorted(note.cc_averages.items())
    )
    return "_".join(parts) + ".wav"


def index_width(notes: list[ManifestNote]) -> int:
    maximum = max((note.render_index for note in notes), default=0)
    return max(4, len(str(maximum)))


def _format_value(value: float, decimals: int) -> str:
    text = f"{value:.{decimals}f}"
    if decimals:
        text = text.rstrip("0").rstrip(".")
    return text.replace("-", "m").replace(".", "p")
