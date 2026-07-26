from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ManifestNote:
    render_index: int
    pitch: int
    velocity: int
    cc_averages: dict[int, float]
    start_seconds: float
    release_end_seconds: float


@dataclass(frozen=True, slots=True)
class TrimConfig:
    pre_roll_seconds: float = 0.0
    post_roll_seconds: float = 0.0
    cc_decimals: int = 3
    overwrite: bool = False


@dataclass(frozen=True, slots=True)
class TrimmedSample:
    note: ManifestNote
    output_path: Path
    start_frame: int
    end_frame: int
    start_seconds: float
    end_seconds: float
    start_clamped: bool
    end_clamped: bool


@dataclass(frozen=True, slots=True)
class TrimResult:
    sample_rate: int
    source_frame_count: int
    samples: tuple[TrimmedSample, ...]
