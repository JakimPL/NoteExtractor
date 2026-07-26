from __future__ import annotations

import argparse
from pathlib import Path

from .models import TrimConfig
from .pipeline import trim_note_stream


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        result = trim_note_stream(
            args.wav,
            args.manifest,
            args.output_directory,
            TrimConfig(
                pre_roll_seconds=args.pre_roll_ms / 1000,
                post_roll_seconds=args.post_roll_ms / 1000,
                cc_decimals=args.cc_decimals,
                overwrite=args.overwrite,
            ),
        )
    except (ValueError, FileExistsError, OSError) as exc:
        parser.error(str(exc))

    clamped = sum(sample.start_clamped or sample.end_clamped for sample in result.samples)
    print(f"wrote {len(result.samples)} samples to {args.output_directory}")
    print(f"sample rate: {result.sample_rate} Hz")
    if clamped:
        print(f"segments clamped to WAV bounds: {clamped}")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="stream-note-trimmer")
    parser.add_argument("wav", type=Path)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("output_directory", type=Path)
    parser.add_argument("--pre-roll-ms", type=_non_negative_float, default=0.0)
    parser.add_argument("--post-roll-ms", type=_non_negative_float, default=0.0)
    parser.add_argument("--cc-decimals", type=_cc_decimals, default=3)
    parser.add_argument("--overwrite", action="store_true")
    return parser


def _non_negative_float(value: str) -> float:
    number = float(value)
    if number < 0:
        raise argparse.ArgumentTypeError("value must not be negative")
    return number


def _cc_decimals(value: str) -> int:
    number = int(value)
    if not 0 <= number <= 9:
        raise argparse.ArgumentTypeError("value must be in 0..9")
    return number
