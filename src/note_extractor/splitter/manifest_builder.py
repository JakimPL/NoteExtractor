from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from ..manifest.models import (
    ManifestSettings,
    NoteManifest,
    NoteRecord,
    NoteTiming,
    RenderInfo,
    RenderTiming,
    SourceInfo,
)
from ..timeline.meter import MeterMap
from ..timeline.tempo import TempoMap
from .arrangement.layout import RenderedNote
from .config import RenderSettings

PITCH_CLASS_NAMES: Final = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
LOWEST_OCTAVE: Final = -1


@dataclass(frozen=True, slots=True)
class PerformanceTiming:
    """Tempo and meter of one performance, placing a stretch of its ticks in seconds and measures."""

    tempo: TempoMap
    meter: MeterMap

    def timing_of(self, start_tick: int, key_end_tick: int, release_end_tick: int) -> NoteTiming:
        """Where the three moments bounding one note sit along this performance."""
        return NoteTiming(
            start_tick=start_tick,
            key_end_tick=key_end_tick,
            release_end_tick=release_end_tick,
            onset_measures=self.meter.measures_at(start_tick),
            key_duration_measures=self.meter.measures_between(start_tick, key_end_tick),
            release_duration_measures=self.meter.measures_between(start_tick, release_end_tick),
            start_seconds=self.tempo.seconds_at(start_tick),
            key_end_seconds=self.tempo.seconds_at(key_end_tick),
            release_end_seconds=self.tempo.seconds_at(release_end_tick),
        )


class ManifestBuilder:
    """Builds the manifest tying the notes of one performance to the render laid out from them.

    The source timing places each note where it was played and the render timing places it where it
    was laid out, which is the pairing the trimmer reads to cut one sample per note.
    """

    def __init__(self, settings: RenderSettings, source: PerformanceTiming, render: PerformanceTiming) -> None:
        self._settings = settings
        self._source = source
        self._render = render

    def build(
        self,
        source_path: Path,
        render_path: Path,
        rendered_notes: Sequence[RenderedNote],
        control_averages: Mapping[int, Mapping[int, float]],
    ) -> NoteManifest:
        """Manifest of one run, holding its notes in the order they were laid out.

        `control_averages` states the average each tracked controller held while a note sounded,
        keyed by the note's source id.
        """
        return NoteManifest(
            settings=ManifestSettings(
                tracked_ccs=tuple(sorted(self._settings.tracked_ccs)),
                cc_channels=tuple(sorted(self._settings.cc_channels)),
                sustain_pedal=self._settings.sustain_pedal,
                rolls=self._settings.rolls,
            ),
            source=SourceInfo(path=source_path, ticks_per_beat=self._settings.ticks_per_beat),
            render=RenderInfo(
                path=render_path,
                tempo_bpm=self._settings.tempo_bpm,
                time_signature=str(self._settings.signature),
                gap_measures=self._settings.gap_measures,
            ),
            notes=tuple(
                self._record(rendered, control_averages[rendered.note.source_id]) for rendered in rendered_notes
            ),
        )

    def _record(self, rendered: RenderedNote, control_averages: Mapping[int, float]) -> NoteRecord:
        """One note's record, stating where it was played alongside where it was laid out."""
        note = rendered.note
        return NoteRecord(
            source_id=note.source_id,
            channel=note.channel,
            pitch=note.pitch,
            pitch_name=pitch_name(note.pitch),
            velocity=note.velocity,
            release_velocity=note.release_velocity,
            cc_averages={control: control_averages[control] for control in sorted(control_averages)},
            source=self._source.timing_of(note.start.tick, note.key_end.tick, note.release_end.tick),
            render=RenderTiming.at_index(
                rendered.render_index,
                self._render.timing_of(rendered.start_tick, rendered.key_end_tick, rendered.release_end_tick),
            ),
        )


def pitch_name(pitch: int) -> str:
    """Pitch class and octave one MIDI pitch sounds, written the way a score names it.

    Middle C, pitch 60, reads as `C4`.
    """
    octave = pitch // len(PITCH_CLASS_NAMES) + LOWEST_OCTAVE
    return f"{PITCH_CLASS_NAMES[pitch % len(PITCH_CLASS_NAMES)]}{octave}"
