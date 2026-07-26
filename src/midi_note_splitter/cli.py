import argparse
from pathlib import Path

from .pipeline import SplitConfig, split_midi
from .timing import parse_time_signature


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        numerator, denominator = parse_time_signature(args.time_signature)
        tracked_ccs = _parse_int_set(args.cc, 0, 127, "CC")
        cc_channels = (
            None
            if args.cc_channels is None
            else _parse_int_set(
                args.cc_channels,
                0,
                15,
                "channel",
            )
        )
        config = SplitConfig(
            tempo_bpm=args.tempo,
            time_signature_numerator=numerator,
            time_signature_denominator=denominator,
            tracked_ccs=frozenset(tracked_ccs),
            cc_channels=None if cc_channels is None else frozenset(cc_channels),
            gap_measures=args.gap_measures,
            sustain_pedal=not args.no_sustain_pedal,
        )
        manifest_path = args.manifest or args.output.with_suffix(".notes.json")
        manifest = split_midi(args.input, args.output, manifest_path, config)
    except ValueError as exception:
        parser.error(str(exception))

    print(f"wrote {args.output}")
    print(f"wrote {manifest_path}")
    print(f"notes: {manifest['config']['note_count']}")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="midi-note-splitter")
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--tempo", type=_positive_float, default=120.0)
    parser.add_argument("--time-signature", default="4/4")
    parser.add_argument("--cc", default="0,1")
    parser.add_argument("--cc-channels")
    parser.add_argument("--gap-measures", type=_non_negative_float, default=0.25)
    parser.add_argument("--no-sustain-pedal", action="store_true")
    return parser


def _parse_int_set(value: str, minimum: int, maximum: int, label: str) -> set[int]:
    result: set[int] = set()
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue

        number = int(part)
        if not minimum <= number <= maximum:
            raise ValueError(f"{label} must be in {minimum}..{maximum}: {number}")

        result.add(number)

    return result


def _positive_float(value: str) -> float:
    number = float(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("value must be positive")

    return number


def _non_negative_float(value: str) -> float:
    number = float(value)
    if number < 0:
        raise argparse.ArgumentTypeError("value must not be negative")

    return number
