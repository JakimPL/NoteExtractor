from dataclasses import dataclass
from pathlib import Path

from .arrange import ArrangementConfig, arrange_notes
from .controllers import ControllerTimeline
from .extract import extract_notes
from .manifest import build_manifest, write_manifest
from .midi_io import load_midi
from .timing import TempoMap, TimeSignatureMap


@dataclass(frozen=True, slots=True)
class SplitConfig:
    tempo_bpm: float = 120.0
    time_signature_numerator: int = 4
    time_signature_denominator: int = 4
    tracked_ccs: frozenset[int] = frozenset({0, 1})
    cc_channels: frozenset[int] | None = None
    gap_measures: float = 0.25
    sustain_pedal: bool = True


def split_midi(
    input_path: Path,
    output_path: Path,
    manifest_path: Path,
    config: SplitConfig,
) -> dict[str, object]:
    parsed = load_midi(input_path)
    controllers = ControllerTimeline(parsed.controller_events)
    notes = extract_notes(parsed, config.sustain_pedal)

    source_tempo = TempoMap.from_events(parsed.ticks_per_beat, parsed.events)
    source_signature = TimeSignatureMap.from_events(parsed.ticks_per_beat, parsed.events)

    for note in notes:
        note.cc_averages = {
            control: controllers.time_weighted_average(
                note.channel,
                control,
                note.start_key,
                note.release_end_key,
                source_tempo,
            )
            for control in sorted(config.tracked_ccs)
            if config.sustain_pedal or control != 64
        }

    cc_channels = parsed.note_channels if config.cc_channels is None else config.cc_channels
    arrangement_config = ArrangementConfig(
        bpm=config.tempo_bpm,
        numerator=config.time_signature_numerator,
        denominator=config.time_signature_denominator,
        gap_measures=config.gap_measures,
        tracked_ccs=config.tracked_ccs,
        cc_channels=cc_channels,
        sustain_pedal=config.sustain_pedal,
    )
    output_midi, rendered_notes = arrange_notes(
        notes,
        parsed.ticks_per_beat,
        controllers,
        arrangement_config,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_midi.save(output_path)

    output_tempo = TempoMap.constant(parsed.ticks_per_beat, config.tempo_bpm)
    output_signature = TimeSignatureMap.constant(
        parsed.ticks_per_beat,
        config.time_signature_numerator,
        config.time_signature_denominator,
    )
    manifest_config = {
        "input": str(input_path),
        "output": str(output_path),
        "ticks_per_beat": parsed.ticks_per_beat,
        "tempo_bpm": config.tempo_bpm,
        "time_signature": f"{config.time_signature_numerator}/{config.time_signature_denominator}",
        "tracked_ccs": sorted(config.tracked_ccs),
        "cc_channels": sorted(cc_channels),
        "gap_measures": config.gap_measures,
        "sustain_pedal": config.sustain_pedal,
        "note_count": len(notes),
    }
    manifest = build_manifest(
        notes,
        rendered_notes,
        source_tempo,
        source_signature,
        output_tempo,
        output_signature,
        manifest_config,
    )
    write_manifest(manifest_path, manifest)
    return manifest
