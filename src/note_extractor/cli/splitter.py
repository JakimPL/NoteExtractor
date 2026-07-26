import argparse
from collections.abc import Sequence
from pathlib import Path
from typing import Final

from pydantic import ValidationError

from ..errors import NoteExtractorError
from ..splitter.config import (
    DEFAULT_GAP_MEASURES,
    DEFAULT_RENDER_SIGNATURE,
    DEFAULT_SUSTAIN_PEDAL,
    DEFAULT_TEMPO_BPM,
    DEFAULT_TRACKED_CCS,
    SplitConfig,
)
from ..splitter.pipeline import split_midi
from .parsing import (
    channel_numbers,
    configuration_failure,
    controller_numbers,
    non_negative_float,
    positive_float,
    time_signature,
)
from .reporting import SUCCESS_EXIT_CODE, report_failure

PROGRAM_NAME: Final = "midi-note-splitter"
MANIFEST_SUFFIX: Final = ".notes.json"


def main(argv: Sequence[str] | None = None) -> int:
    """Run the splitter over the command line it is given.

    Returns:
        `SUCCESS_EXIT_CODE` once the render and its manifest are written, and `FAILURE_EXIT_CODE`
        when the run reports why it wrote neither.
    """
    arguments = _build_parser().parse_args(argv)
    try:
        return _split(arguments)
    except NoteExtractorError as error:
        return report_failure(PROGRAM_NAME, error)


def _split(arguments: argparse.Namespace) -> int:
    """Carry out one split run and state where it wrote.

    Raises:
        ConfigurationError: If a setting falls outside the range it supports.
        MidiSourceError: If the source resists parsing or states timing the reader leaves unsupported.
        RenderError: If the render resists writing.
        ManifestError: If the manifest resists writing.
    """
    manifest_path = arguments.manifest or arguments.output.with_suffix(MANIFEST_SUFFIX)
    manifest = split_midi(arguments.input, arguments.output, manifest_path, _config(arguments))

    print(f"wrote {arguments.output}")
    print(f"wrote {manifest_path}")
    print(f"notes: {len(manifest.notes)}")
    return SUCCESS_EXIT_CODE


def _config(arguments: argparse.Namespace) -> SplitConfig:
    """Settings one command line states.

    Raises:
        ConfigurationError: If a setting falls outside the range it supports.
    """
    try:
        return SplitConfig(
            tempo_bpm=arguments.tempo,
            signature=arguments.time_signature,
            tracked_ccs=arguments.cc,
            cc_channels=arguments.cc_channels,
            gap_measures=arguments.gap_measures,
            sustain_pedal=arguments.sustain_pedal,
        )
    except ValidationError as error:
        raise configuration_failure(error) from error


def _build_parser() -> argparse.ArgumentParser:
    """Flags the splitter takes, together with the settings it falls back on."""
    parser = argparse.ArgumentParser(
        prog=PROGRAM_NAME,
        description="Split a MIDI performance into a render sounding one note at a time.",
    )
    parser.add_argument("input", type=Path, help="MIDI performance to extract the notes from")
    parser.add_argument("output", type=Path, help="MIDI render to write the isolated notes to")
    parser.add_argument(
        "--manifest",
        type=Path,
        help=f"where to write the note timings, by default the render named with {MANIFEST_SUFFIX}",
    )
    parser.add_argument(
        "--tempo",
        type=positive_float,
        default=DEFAULT_TEMPO_BPM,
        metavar="BPM",
        help="beats per minute the render is laid out at",
    )
    parser.add_argument(
        "--time-signature",
        type=time_signature,
        default=DEFAULT_RENDER_SIGNATURE,
        metavar="N/D",
        help="time signature the render is laid out on",
    )
    parser.add_argument(
        "--cc",
        type=controller_numbers,
        default=DEFAULT_TRACKED_CCS,
        metavar="LIST",
        help="controllers each rendered note opens with and the manifest averages",
    )
    parser.add_argument(
        "--cc-channels",
        type=channel_numbers,
        metavar="LIST",
        help="channels whose controllers reach the render, by default those carrying notes",
    )
    parser.add_argument(
        "--gap-measures",
        type=non_negative_float,
        default=DEFAULT_GAP_MEASURES,
        metavar="MEASURES",
        help="space left between one note's release and the next note's onset",
    )
    parser.add_argument(
        "--sustain-pedal",
        action=argparse.BooleanOptionalAction,
        default=DEFAULT_SUSTAIN_PEDAL,
        help="hold each note as long as the pedal did, rather than to its key release",
    )
    return parser


if __name__ == "__main__":
    raise SystemExit(main())
