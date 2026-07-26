import argparse
from collections.abc import Sequence
from pathlib import Path
from typing import Final

from pydantic import ValidationError

from ..errors import NoteExtractorError
from ..trimmer.config import (
    DEFAULT_CC_DECIMALS,
    DEFAULT_OVERWRITE,
    DEFAULT_POST_ROLL_SECONDS,
    DEFAULT_PRE_ROLL_SECONDS,
    TrimConfig,
)
from ..trimmer.pipeline import trim_note_stream
from .parsing import configuration_failure, decimal_places, non_negative_float
from .reporting import SUCCESS_EXIT_CODE, report_failure

PROGRAM_NAME: Final = "stream-note-trimmer"
MILLISECONDS_PER_SECOND: Final = 1000.0


def main(argv: Sequence[str] | None = None) -> int:
    """Run the trimmer over the command line it is given.

    Returns:
        `SUCCESS_EXIT_CODE` once every sample is written, and `FAILURE_EXIT_CODE` when the run
        reports why it cut none.
    """
    arguments = _build_parser().parse_args(argv)
    try:
        return _trim(arguments)
    except NoteExtractorError as error:
        return report_failure(PROGRAM_NAME, error)


def _trim(arguments: argparse.Namespace) -> int:
    """Carry out one trim run and state what it cut.

    Raises:
        ConfigurationError: If a setting falls outside the range it supports.
        ManifestError: If the manifest is unreadable or falls outside the schema.
        AudioError: If the stream is unreadable, or ends before a note the manifest places.
        OutputConflictError: If two notes claim one file, or a file an earlier run wrote is kept.
    """
    result = trim_note_stream(arguments.wav, arguments.manifest, arguments.output_directory, _config(arguments))

    print(f"wrote {len(result.samples)} samples to {arguments.output_directory}")
    print(f"sample rate: {result.sample_rate} Hz")
    if result.clamped_count:
        print(f"segments clamped to WAV bounds: {result.clamped_count}")

    return SUCCESS_EXIT_CODE


def _config(arguments: argparse.Namespace) -> TrimConfig:
    """Settings one command line states, with the rolls read as milliseconds.

    Raises:
        ConfigurationError: If a setting falls outside the range it supports.
    """
    try:
        return TrimConfig(
            pre_roll_seconds=arguments.pre_roll_ms / MILLISECONDS_PER_SECOND,
            post_roll_seconds=arguments.post_roll_ms / MILLISECONDS_PER_SECOND,
            cc_decimals=arguments.cc_decimals,
            overwrite=arguments.overwrite,
        )
    except ValidationError as error:
        raise configuration_failure(error) from error


def _build_parser() -> argparse.ArgumentParser:
    """Flags the trimmer takes, together with the settings it falls back on."""
    parser = argparse.ArgumentParser(
        prog=PROGRAM_NAME,
        description="Cut a rendered WAV into one sample per note of its manifest.",
    )
    parser.add_argument("wav", type=Path, help="audio rendered from the isolated note MIDI")
    parser.add_argument("manifest", type=Path, help="note timings the splitter wrote beside the render")
    parser.add_argument("output_directory", type=Path, help="directory to write the samples to")
    parser.add_argument(
        "--pre-roll-ms",
        type=non_negative_float,
        default=DEFAULT_PRE_ROLL_SECONDS * MILLISECONDS_PER_SECOND,
        metavar="MS",
        help="audio kept ahead of each onset",
    )
    parser.add_argument(
        "--post-roll-ms",
        type=non_negative_float,
        default=DEFAULT_POST_ROLL_SECONDS * MILLISECONDS_PER_SECOND,
        metavar="MS",
        help="audio kept past the moment each note was let go of",
    )
    parser.add_argument(
        "--cc-decimals",
        type=decimal_places,
        default=DEFAULT_CC_DECIMALS,
        metavar="PLACES",
        help="decimal places a controller average keeps in a sample file name",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        default=DEFAULT_OVERWRITE,
        help="replace the samples an earlier run wrote",
    )
    return parser


if __name__ == "__main__":
    raise SystemExit(main())
