from __future__ import annotations

import json
from pathlib import Path

from .models import ManifestNote


def load_manifest(path: Path) -> list[ManifestNote]:
    data = json.loads(path.read_text(encoding="utf-8"))
    raw_notes = data.get("notes")
    if not isinstance(raw_notes, list):
        raise ValueError("manifest must contain a notes list")

    notes = [_parse_note(raw, position) for position, raw in enumerate(raw_notes)]
    notes.sort(key=lambda note: note.render_index)
    _validate_render_indices(notes)
    return notes


def _parse_note(raw: object, position: int) -> ManifestNote:
    if not isinstance(raw, dict):
        raise ValueError(f"manifest note {position} must be an object")

    render = raw.get("render")
    cc_averages = raw.get("cc_averages", {})
    if not isinstance(render, dict):
        raise ValueError(f"manifest note {position} has no render object")
    if not isinstance(cc_averages, dict):
        raise ValueError(f"manifest note {position} has invalid cc_averages")

    try:
        note = ManifestNote(
            render_index=int(render["index"]),
            pitch=int(raw["pitch"]),
            velocity=int(raw["velocity"]),
            cc_averages={int(control): float(value) for control, value in cc_averages.items()},
            start_seconds=float(render["start_seconds"]),
            release_end_seconds=float(render["release_end_seconds"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"manifest note {position} has invalid fields") from exc

    if not 0 <= note.pitch <= 127:
        raise ValueError(f"manifest note {position} pitch must be in 0..127")
    if not 0 <= note.velocity <= 127:
        raise ValueError(f"manifest note {position} velocity must be in 0..127")
    if note.start_seconds < 0:
        raise ValueError(f"manifest note {position} starts before zero")
    if note.release_end_seconds <= note.start_seconds:
        raise ValueError(f"manifest note {position} has a non-positive duration")
    return note


def _validate_render_indices(notes: list[ManifestNote]) -> None:
    indices = [note.render_index for note in notes]
    if len(indices) != len(set(indices)):
        raise ValueError("manifest contains duplicate render indices")
