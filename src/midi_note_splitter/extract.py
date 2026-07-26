from __future__ import annotations

from collections import defaultdict, deque

from .models import Note, ParsedMidi


def extract_notes(parsed: ParsedMidi, sustain_pedal: bool) -> list[Note]:
    active: dict[tuple[int, int], deque[Note]] = defaultdict(deque)
    sustained: dict[int, list[Note]] = defaultdict(list)
    pedal_down: dict[int, bool] = defaultdict(bool)
    notes: list[Note] = []

    for event in parsed.events:
        message = event.message

        if message.type == "control_change" and message.control == 64 and sustain_pedal:
            was_down = pedal_down[message.channel]
            is_down = message.value >= 64
            pedal_down[message.channel] = is_down
            if was_down and not is_down:
                for note in sustained.pop(message.channel, []):
                    _finish_release(note, event.tick, event.sequence)
            continue

        if message.type == "note_on" and message.velocity > 0:
            note = Note(
                source_id=len(notes),
                channel=message.channel,
                pitch=message.note,
                velocity=message.velocity,
                start_tick=event.tick,
                start_sequence=event.sequence,
            )
            notes.append(note)
            active[(message.channel, message.note)].append(note)
            continue

        is_note_off = message.type == "note_off" or (message.type == "note_on" and message.velocity == 0)
        if not is_note_off:
            continue

        queue = active[(message.channel, message.note)]
        if not queue:
            continue

        note = queue.popleft()
        note.key_end_tick = event.tick
        note.key_end_sequence = event.sequence
        note.release_velocity = message.velocity

        if sustain_pedal and pedal_down[message.channel]:
            sustained[message.channel].append(note)
        else:
            _finish_release(note, event.tick, event.sequence)

    for queue in active.values():
        while queue:
            note = queue.popleft()
            note.key_end_tick = parsed.end_tick
            note.key_end_sequence = parsed.end_sequence
            _finish_release(note, parsed.end_tick, parsed.end_sequence)

    for channel_notes in sustained.values():
        for note in channel_notes:
            _finish_release(note, parsed.end_tick, parsed.end_sequence)

    return notes


def _finish_release(note: Note, tick: int, sequence: int) -> None:
    note.release_end_tick = tick
    note.release_end_sequence = sequence
