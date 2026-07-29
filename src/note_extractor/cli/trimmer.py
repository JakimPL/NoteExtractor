import argparse
from collections.abc import Sequence
from pathlib import Path
from typing import Final

from ..config import load_config
from ..errors import NoteExtractorError
from ..trimmer.config import TrimConfig
from ..trimmer.pipeline import trim_note_stream
from .reporting import SUCCESS_EXIT_CODE, report_failure

PROGRAM_NAME: Final = "stream-note-trimmer"


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
        ConfigurationError: If the configuration resists reading, or states a setting outside the
            range it supports.
        ManifestError: If the manifest is unreadable or falls outside the schema.
        AudioError: If the stream is unreadable, or ends before a note the manifest places.
        OutputConflictError: If two notes claim one file, or a file an earlier run wrote is kept.
    """
    config = TrimConfig.from_document(load_config(arguments.config), overwrite=arguments.overwrite)
    result = trim_note_stream(arguments.wav, arguments.manifest, arguments.output_directory, config)

    print(f"wrote {len(result.samples)} samples to {arguments.output_directory}")
    print(f"sample rate: {result.sample_rate} Hz")
    if result.clamped_count:
        print(f"segments clamped to WAV bounds: {result.clamped_count}")

    return SUCCESS_EXIT_CODE


def _build_parser() -> argparse.ArgumentParser:
    """Paths the trimmer reads and writes, where it takes its settings from, and what it may replace."""
    parser = argparse.ArgumentParser(
        prog=PROGRAM_NAME,
        description="Cut a rendered WAV into one sample per note of its manifest.",
    )
    parser.add_argument("wav", type=Path, help="audio rendered from the isolated note MIDI")
    parser.add_argument("manifest", type=Path, help="note timings the splitter wrote beside the render")
    parser.add_argument("output_directory", type=Path, help="directory to write the samples to")
    parser.add_argument(
        "--config",
        type=Path,
        metavar="PATH",
        help="settings to carry the run out under, by default the ones shipped with the tool",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="replace the samples an earlier run wrote",
    )
    return parser


if __name__ == "__main__":
    raise SystemExit(main())
