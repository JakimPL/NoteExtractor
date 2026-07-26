from __future__ import annotations

import math
from pathlib import Path

from tqdm import tqdm

from .audio import read_wav, write_wav
from .manifest import load_manifest
from .models import ManifestNote, TrimConfig, TrimmedSample, TrimResult
from .naming import index_width, sample_filename


def trim_note_stream(
    wav_path: Path,
    manifest_path: Path,
    output_directory: Path,
    config: TrimConfig = TrimConfig(),
) -> TrimResult:
    _validate_config(config)
    notes = load_manifest(manifest_path)
    sample_rate, audio = read_wav(wav_path)
    frame_count = len(audio)
    width = index_width(notes)
    planned = [_plan_sample(note, output_directory, sample_rate, frame_count, config, width) for note in notes]
    _validate_outputs(planned, config.overwrite)

    output_directory.mkdir(parents=True, exist_ok=True)
    for sample in tqdm(planned):
        write_wav(
            sample.output_path,
            sample_rate,
            audio[sample.start_frame : sample.end_frame],
        )

    return TrimResult(
        sample_rate=sample_rate,
        source_frame_count=frame_count,
        samples=tuple(planned),
    )


def _plan_sample(
    note: ManifestNote,
    output_directory: Path,
    sample_rate: int,
    frame_count: int,
    config: TrimConfig,
    width: int,
) -> TrimmedSample:
    requested_start = note.start_seconds - config.pre_roll_seconds
    requested_end = note.release_end_seconds + config.post_roll_seconds
    raw_start_frame = math.floor(requested_start * sample_rate)
    raw_end_frame = math.ceil(requested_end * sample_rate)
    start_frame = max(0, raw_start_frame)
    end_frame = min(frame_count, raw_end_frame)

    if start_frame >= frame_count:
        raise ValueError(f"note {note.render_index} starts after the WAV ends: {note.start_seconds:.6f}s")
    if end_frame <= start_frame:
        raise ValueError(f"note {note.render_index} produces an empty WAV segment")

    return TrimmedSample(
        note=note,
        output_path=output_directory / sample_filename(note, config.cc_decimals, width),
        start_frame=start_frame,
        end_frame=end_frame,
        start_seconds=start_frame / sample_rate,
        end_seconds=end_frame / sample_rate,
        start_clamped=start_frame != raw_start_frame,
        end_clamped=end_frame != raw_end_frame,
    )


def _validate_config(config: TrimConfig) -> None:
    if config.pre_roll_seconds < 0:
        raise ValueError("pre-roll must not be negative")
    if config.post_roll_seconds < 0:
        raise ValueError("post-roll must not be negative")
    if not 0 <= config.cc_decimals <= 9:
        raise ValueError("CC decimals must be in 0..9")


def _validate_outputs(samples: list[TrimmedSample], overwrite: bool) -> None:
    paths = [sample.output_path for sample in samples]
    if len(paths) != len(set(paths)):
        raise ValueError("generated sample filenames are not unique")
    if overwrite:
        return
    existing = [path for path in paths if path.exists()]
    if existing:
        raise FileExistsError(f"output already exists: {existing[0]}")
