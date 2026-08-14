import pytest
from pydantic import ValidationError

from note_extractor.errors import MidiSourceError
from note_extractor.midi.events import EventPosition
from note_extractor.splitter.arrangement.layout import RenderedNote, lay_out_notes
from note_extractor.splitter.notes import SourceNote


def test_the_first_note_of_a_render_opens_it() -> None:
    laid_out = lay_out_notes([_note(source_id=0, pitch=60, key_ticks=480, release_ticks=720)], gap_ticks=240)

    assert laid_out[0].start_tick == 0
    assert laid_out[0].key_end_tick == 480
    assert laid_out[0].release_end_tick == 720


def test_each_note_follows_the_release_of_the_one_before_it_across_the_gap() -> None:
    laid_out = lay_out_notes(
        [
            _note(source_id=0, pitch=60, key_ticks=480, release_ticks=720),
            _note(source_id=1, pitch=62, key_ticks=240, release_ticks=240),
        ],
        gap_ticks=240,
    )

    assert [(note.start_tick, note.key_end_tick, note.release_end_tick) for note in laid_out] == [
        (0, 480, 720),
        (960, 1200, 1200),
    ]


def test_every_note_keeps_the_spans_it_sounds_over() -> None:
    note = _note(source_id=0, pitch=60, key_ticks=480, release_ticks=720)
    laid_out = lay_out_notes([_note(source_id=1, pitch=59, key_ticks=120, release_ticks=120), note], gap_ticks=100)

    placed = next(item for item in laid_out if item.note is note)

    assert placed.key_end_tick - placed.start_tick == note.key_duration_ticks
    assert placed.release_end_tick - placed.start_tick == note.release_duration_ticks


def test_notes_are_indexed_in_the_order_they_were_laid_out() -> None:
    laid_out = lay_out_notes(
        [
            _note(source_id=0, pitch=72, key_ticks=480, release_ticks=480),
            _note(source_id=1, pitch=60, key_ticks=480, release_ticks=480),
        ],
        gap_ticks=480,
    )

    assert [note.render_index for note in laid_out] == [0, 1]
    assert [note.note.pitch for note in laid_out] == [60, 72]


def test_a_render_of_no_notes_is_empty() -> None:
    assert not lay_out_notes([], gap_ticks=480)


def test_a_note_let_go_of_where_it_starts_is_reported_against_its_place_in_the_source() -> None:
    """Nothing sounds over an empty stretch, so no sample could be cut from it either."""
    notes = [
        _note(source_id=0, pitch=60, key_ticks=480, release_ticks=480),
        _note(source_id=1, pitch=64, key_ticks=0, release_ticks=0),
    ]

    with pytest.raises(MidiSourceError, match="note 1 sounds over no ticks: pitch 64 at tick 0"):
        lay_out_notes(notes, gap_ticks=480)


def test_a_placement_ending_before_it_starts_is_rejected() -> None:
    with pytest.raises(ValidationError, match="must end from its start onwards"):
        RenderedNote(
            render_index=0,
            note=_note(source_id=0, pitch=60, key_ticks=480, release_ticks=480),
            start_tick=960,
            key_end_tick=480,
            release_end_tick=1440,
        )


def _note(source_id: int, pitch: int, key_ticks: int, release_ticks: int) -> SourceNote:
    return SourceNote(
        source_id=source_id,
        channel=0,
        pitch=pitch,
        velocity=100,
        release_velocity=0,
        start=EventPosition(tick=0, sequence=source_id),
        key_end=EventPosition(tick=key_ticks, sequence=source_id + 10),
        release_end=EventPosition(tick=release_ticks, sequence=source_id + 20),
    )
