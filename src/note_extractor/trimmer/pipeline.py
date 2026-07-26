from collections.abc import Sequence
from pathlib import Path

from pydantic import Field
from tqdm import tqdm

from ..manifest.storage import read_manifest
from ..models import FrozenModel
from .audio import AudioStream, read_wav, write_wav
from .config import TrimConfig
from .naming import SampleNaming
from .planning import SamplePlanner, TrimmedSample


class TrimResult(FrozenModel):
    """Outcome of one trim run: the stream it read and the samples it cut from it."""

    sample_rate: int = Field(gt=0)
    source_frame_count: int = Field(ge=0)
    samples: tuple[TrimmedSample, ...]

    @property
    def clamped_count(self) -> int:
        """Samples holding less audio than the rolls reached for, the stream having run out."""
        return sum(sample.start_clamped or sample.end_clamped for sample in self.samples)


def trim_note_stream(
    wav_path: Path,
    manifest_path: Path,
    output_directory: Path,
    config: TrimConfig,
) -> TrimResult:
    """Cut one rendered stream into the per-note samples its manifest places.

    Each note of the manifest names one file under `output_directory`, holding the stretch of audio
    the note sounds over widened by the rolls the run asks for.

    Raises:
        ManifestError: If the manifest resists reading or falls outside the schema.
        AudioError: If the stream resists reading, or ends before a note the manifest places.
        OutputConflictError: If two notes claim one file, or a file an earlier run wrote is kept.
    """
    notes = read_manifest(manifest_path).notes_in_render_order()
    stream = read_wav(wav_path)
    naming = SampleNaming.for_notes(notes, config.cc_decimals)
    samples = SamplePlanner(config, naming, output_directory).plan(notes, stream)
    _write_samples(output_directory, stream, samples)

    return TrimResult(
        sample_rate=stream.sample_rate,
        source_frame_count=stream.frame_count,
        samples=samples,
    )


def _write_samples(output_directory: Path, stream: AudioStream, samples: Sequence[TrimmedSample]) -> None:
    """Write one WAV file per planned sample, creating the directories leading up to them.

    Raises:
        AudioError: If a sample file resists writing.
    """
    output_directory.mkdir(parents=True, exist_ok=True)
    for sample in tqdm(samples):
        write_wav(sample.output_path, stream.segment(sample.start_frame, sample.end_frame))
