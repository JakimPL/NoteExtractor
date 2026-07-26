from pathlib import Path

import numpy as np
import numpy.typing as npt
import pytest
from scipy.io import wavfile

from note_extractor.errors import AudioError
from note_extractor.trimmer.audio import AudioStream, read_wav, write_wav

from .conftest import SAMPLE_RATE, ramp, stream_of


def test_mono_frames_survive_a_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "mono.wav"
    write_wav(path, stream_of(ramp(500)))

    stream = read_wav(path)

    assert stream.sample_rate == SAMPLE_RATE
    assert stream.frame_count == 500
    assert stream.samples.dtype == np.int16
    np.testing.assert_array_equal(stream.samples, ramp(500))


def test_stereo_frames_keep_both_channels(tmp_path: Path) -> None:
    path = tmp_path / "stereo.wav"
    frames = _stereo(400)
    write_wav(path, stream_of(frames))

    stream = read_wav(path)

    assert stream.frame_count == 400
    assert stream.samples.shape == (400, 2)
    np.testing.assert_array_equal(stream.samples, frames)


def test_frames_keep_the_type_they_were_recorded_with(tmp_path: Path) -> None:
    """A renderer writing floating point audio has its resolution carried through to the samples."""
    path = tmp_path / "float.wav"
    frames = np.linspace(-1.0, 1.0, 300, dtype=np.float32)
    wavfile.write(path, SAMPLE_RATE, frames)

    stream = read_wav(path)

    assert stream.samples.dtype == np.float32
    np.testing.assert_array_equal(stream.samples, frames)


def test_a_stream_states_the_time_its_frames_sound_for() -> None:
    assert stream_of(ramp(1500)).duration_seconds == 1.5


def test_a_segment_holds_the_frames_it_was_cut_between() -> None:
    segment = stream_of(ramp(500)).segment(100, 150)

    assert segment.sample_rate == SAMPLE_RATE
    assert segment.frame_count == 50
    np.testing.assert_array_equal(segment.samples, np.arange(100, 150, dtype=np.int16))


def test_a_segment_of_stereo_frames_keeps_both_channels() -> None:
    segment = stream_of(_stereo(400)).segment(10, 20)

    assert segment.samples.shape == (10, 2)


@pytest.mark.parametrize("sample_rate", [0, -SAMPLE_RATE])
def test_a_stream_placing_no_frames_in_time_is_rejected(sample_rate: int) -> None:
    with pytest.raises(AudioError, match="places no timing"):
        AudioStream(sample_rate=sample_rate, samples=ramp(100))


def test_audio_stating_no_sample_rate_is_reported(tmp_path: Path) -> None:
    """A header a renderer left unfilled would place every note at the same frame."""
    path = tmp_path / "unrated.wav"
    wavfile.write(path, 0, ramp(100))

    with pytest.raises(AudioError, match=f"cannot read audio {path}: a sample rate of 0"):
        read_wav(path)


def test_a_missing_file_is_reported_against_its_path(tmp_path: Path) -> None:
    path = tmp_path / "absent.wav"

    with pytest.raises(AudioError, match=f"cannot read audio {path}"):
        read_wav(path)


def test_bytes_that_hold_no_audio_are_reported(tmp_path: Path) -> None:
    path = tmp_path / "text.wav"
    path.write_text("this is not a WAV file", encoding="utf-8")

    with pytest.raises(AudioError, match="cannot read audio"):
        read_wav(path)


def test_a_stream_is_written_where_it_is_asked_for(tmp_path: Path) -> None:
    path = tmp_path / "written.wav"

    write_wav(path, stream_of(ramp(64)))

    rate, frames = wavfile.read(path)
    assert rate == SAMPLE_RATE
    np.testing.assert_array_equal(frames, ramp(64))


def test_a_path_that_resists_writing_is_reported(tmp_path: Path) -> None:
    path = tmp_path / "absent-directory" / "sample.wav"

    with pytest.raises(AudioError, match=f"cannot write audio {path}"):
        write_wav(path, stream_of(ramp(10)))


def _stereo(frame_count: int) -> npt.NDArray[np.int16]:
    """Frames whose channels count in opposite directions, so each one states its own side."""
    return np.column_stack((ramp(frame_count), -ramp(frame_count)))
