from pathlib import Path

from ..manifest.models import NoteManifest
from ..manifest.storage import write_manifest
from ..midi.reader import read_midi
from ..midi.source import SourceMidi
from ..midi.writer import write_midi
from ..timeline.meter import MeterMap
from ..timeline.tempo import TempoMap
from .arrangement.score import arrange_notes
from .cc_averages import average_control_values
from .config import RenderSettings, SplitConfig
from .controllers import ControllerTimeline
from .duration import DurationBounds, sounded_notes
from .extraction import NoteExtractor
from .manifest_builder import ManifestBuilder, PerformanceTiming
from .notes import SourceNote, finalize


def split_midi(
    input_path: Path,
    output_path: Path,
    manifest_path: Path,
    config: SplitConfig,
) -> NoteManifest:
    """Split one performance into a render sounding a single note at a time, plus its manifest.

    The render replays every note of the source in turn, each voiced with the controller settings
    that surrounded it, and the manifest states where each note sits in both performances so a
    renderer's output can be cut back apart.

    Raises:
        MidiSourceError: If the source resists parsing or states timing the reader leaves unsupported.
        RenderError: If the render resists writing.
        ManifestError: If the manifest resists writing.
    """
    source = read_midi(input_path)
    controllers = ControllerTimeline(source.control_changes())
    settings = RenderSettings.from_config(config, source.ticks_per_beat, source.note_channels())
    source_timing = _source_timing(source)

    notes = _sounded_notes(source, config.sustain_pedal, settings.duration_bounds)
    control_averages = {
        note.source_id: average_control_values(
            controllers,
            source_timing.tempo,
            note,
            settings.applied_controls,
        )
        for note in notes
    }

    score, rendered_notes = arrange_notes(notes, controllers, settings)
    write_midi(output_path, score)

    manifest = ManifestBuilder(settings, source_timing, _render_timing(settings)).build(
        input_path,
        output_path,
        rendered_notes,
        control_averages,
    )
    write_manifest(manifest_path, manifest)
    return manifest


def _sounded_notes(
    source: SourceMidi,
    sustain_pedal: bool,
    bounds: DurationBounds,
) -> tuple[SourceNote, ...]:
    """Notes of one performance the run sounds, each over the span its bounds allow.

    A note played too briefly to be worth sampling never reaches the render, and every note the run
    keeps is held on to the shortest span it sounds and let go of at the longest.
    """
    played = (finalize(draft) for draft in NoteExtractor(sustain_pedal).extract(source))
    return sounded_notes(played, bounds)


def _source_timing(source: SourceMidi) -> PerformanceTiming:
    """Timing the source performance states, which its own messages may change as it runs."""
    return PerformanceTiming(
        tempo=TempoMap.from_changes(source.ticks_per_beat, source.tempo_changes()),
        meter=MeterMap.from_changes(source.ticks_per_beat, source.meter_changes()),
    )


def _render_timing(settings: RenderSettings) -> PerformanceTiming:
    """Timing the render is written with, which holds one tempo and one time signature throughout."""
    return PerformanceTiming(
        tempo=TempoMap.constant(settings.ticks_per_beat, settings.tempo_bpm),
        meter=MeterMap.constant(settings.ticks_per_beat, settings.signature),
    )
