from __future__ import annotations

import json
from pathlib import Path

from .models import Note, RenderedNote
from .timing import TempoMap, TimeSignatureMap


def build_manifest(
    notes: list[Note],
    rendered_notes: list[RenderedNote],
    source_tempo: TempoMap,
    source_signature: TimeSignatureMap,
    output_tempo: TempoMap,
    output_signature: TimeSignatureMap,
    config: dict[str, object],
) -> dict[str, object]:
    rendered_by_source = {rendered.note.source_id: rendered for rendered in rendered_notes}
    records = [
        _note_record(
            note,
            rendered_by_source[note.source_id],
            source_tempo,
            source_signature,
            output_tempo,
            output_signature,
        )
        for note in notes
    ]
    records.sort(key=lambda record: record["render"]["index"])
    return {"config": config, "notes": records}


def write_manifest(path: Path, manifest: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def _note_record(
    note: Note,
    rendered: RenderedNote,
    source_tempo: TempoMap,
    source_signature: TimeSignatureMap,
    output_tempo: TempoMap,
    output_signature: TimeSignatureMap,
) -> dict[str, object]:
    source_key_end = note.required_key_end_tick
    source_release_end = note.required_release_end_tick
    return {
        "source_id": note.source_id,
        "channel": note.channel,
        "pitch": note.pitch,
        "pitch_name": _pitch_name(note.pitch),
        "velocity": note.velocity,
        "release_velocity": note.release_velocity,
        "cc_averages": {str(control): value for control, value in sorted(note.cc_averages.items())},
        "source": {
            "start_tick": note.start_tick,
            "key_end_tick": source_key_end,
            "release_end_tick": source_release_end,
            "onset_measures": source_signature.measures_at(note.start_tick),
            "key_duration_measures": source_signature.measures_between(note.start_tick, source_key_end),
            "release_duration_measures": source_signature.measures_between(note.start_tick, source_release_end),
            "start_seconds": source_tempo.seconds_at(note.start_tick),
            "key_end_seconds": source_tempo.seconds_at(source_key_end),
            "release_end_seconds": source_tempo.seconds_at(source_release_end),
        },
        "render": {
            "index": rendered.render_index,
            "start_tick": rendered.start_tick,
            "key_end_tick": rendered.key_end_tick,
            "release_end_tick": rendered.release_end_tick,
            "onset_measures": output_signature.measures_at(rendered.start_tick),
            "key_duration_measures": output_signature.measures_between(rendered.start_tick, rendered.key_end_tick),
            "release_duration_measures": output_signature.measures_between(
                rendered.start_tick, rendered.release_end_tick
            ),
            "start_seconds": output_tempo.seconds_at(rendered.start_tick),
            "key_end_seconds": output_tempo.seconds_at(rendered.key_end_tick),
            "release_end_seconds": output_tempo.seconds_at(rendered.release_end_tick),
        },
    }


def _pitch_name(pitch: int) -> str:
    names = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
    return f"{names[pitch % 12]}{pitch // 12 - 1}"
