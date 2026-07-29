from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Final

import pytest
from mido import Message, MetaMessage, MidiFile, MidiTrack

from note_extractor.config import load_config
from note_extractor.midi.reader import read_midi
from note_extractor.midi.source import SourceMidi
from note_extractor.splitter.config import RenderSettings, SplitConfig
from note_extractor.timeline.meter import TimeSignature

TICKS_PER_BEAT: Final = 480
COMMON_TIME: Final = TimeSignature(numerator=4, denominator=4)
MEASURE_TICKS: Final = 1920

BUNDLED: Final = SplitConfig.from_document(load_config(None))

ReadPerformance = Callable[[Sequence[Message | MetaMessage]], SourceMidi]


@pytest.fixture(name="read_performance")
def fixture_read_performance(tmp_path: Path) -> ReadPerformance:
    """Reader turning messages timed as deltas into the performance the pipeline sees."""

    def read(messages: Sequence[Message | MetaMessage]) -> SourceMidi:
        path = tmp_path / "performance.mid"
        midi = MidiFile(type=1, ticks_per_beat=TICKS_PER_BEAT)
        track = MidiTrack()
        track.extend(messages)
        midi.tracks.append(track)
        midi.save(path)
        return read_midi(path)

    return read


def split_config(**overrides: object) -> SplitConfig:
    """The bundled split settings with the given fields overridden, re-validated.

    Every setting comes from the document the tool ships, so a test states the one knob it is about
    and reads the settings a run is actually carried out under for the rest.
    """
    return SplitConfig.model_validate({**BUNDLED.model_dump(), **overrides})


def settings(config: SplitConfig, note_channels: frozenset[int] = frozenset({0})) -> RenderSettings:
    """Settings the given configuration settles on against a performance of `TICKS_PER_BEAT`."""
    return RenderSettings.from_config(config, TICKS_PER_BEAT, note_channels)
