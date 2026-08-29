"""Schedule parsed events and write MIDI files."""

from __future__ import annotations

from pathlib import Path

import pretty_midi

from swarasynth.gamaka import apply_gamakas, cents_to_pitch_bend
from swarasynth.models import EventKind, ParsedEvent, TimedNote
from swarasynth.tuning import load_raga, swara_to_midi


def events_to_timed_notes(
    events: list[ParsedEvent],
    raga_name: str,
    *,
    beats_per_note: float = 0.5,
    hold_beats: float = 0.5,
    tempo_bpm: float = 60.0,
    ragas_dir: Path | None = None,
    apply_gamaka_rules: bool = False,
    tonic_midi: int | None = None,
) -> list[TimedNote]:
    """Convert parsed events to timed notes (seconds)."""
    raga = load_raga(raga_name, ragas_dir)
    seconds_per_beat = 60.0 / tempo_bpm
    notes: list[TimedNote] = []
    t = 0.0
    last_note_idx: int | None = None

    for ev in events:
        if ev.kind == EventKind.HOLD:
            if last_note_idx is not None:
                extra = hold_beats * seconds_per_beat
                prev = notes[last_note_idx]
                notes[last_note_idx] = TimedNote(
                    pitch=prev.pitch,
                    start=prev.start,
                    duration=prev.duration + extra,
                    velocity=prev.velocity,
                    pitch_bends=prev.pitch_bends,
                )
                t += extra
            else:
                t += hold_beats * seconds_per_beat
            continue

        assert ev.swara is not None
        pitch = swara_to_midi(ev.swara, raga, tonic_midi=tonic_midi)
        dur = beats_per_note * seconds_per_beat
        notes.append(TimedNote(pitch=pitch, start=t, duration=dur))
        last_note_idx = len(notes) - 1
        t += dur

    if apply_gamaka_rules:
        notes = apply_gamakas(notes, events, raga, tonic_midi=tonic_midi)

    return notes


def _note_end_with_legato(
    note: TimedNote,
    next_note: TimedNote | None,
    *,
    legato_overlap: float,
    max_interval_semitones: int = 5,
) -> float:
    """Extend note end for legato on melodic steps (wider for Charukeshi jarus)."""
    end = note.start + note.duration
    if legato_overlap <= 0 or next_note is None:
        return end
    if abs(next_note.pitch - note.pitch) > max_interval_semitones:
        return end
    return max(end, next_note.start + legato_overlap)


def notes_to_pretty_midi(
    notes: list[TimedNote],
    *,
    program: int = 40,
    legato_overlap: float = 0.0,
    legato_overlaps: list[float] | None = None,
    legato_max_interval: int = 5,
) -> pretty_midi.PrettyMIDI:
    """Build a PrettyMIDI score from timed notes (violin default, GM program 40)."""
    pm = pretty_midi.PrettyMIDI()
    instrument = pretty_midi.Instrument(program=program, name="SwaraSynth")
    for i, n in enumerate(notes):
        next_note = notes[i + 1] if i + 1 < len(notes) else None
        overlap = legato_overlap
        if legato_overlaps is not None and i < len(legato_overlaps):
            overlap = legato_overlaps[i]
        end = _note_end_with_legato(
            n,
            next_note,
            legato_overlap=overlap,
            max_interval_semitones=legato_max_interval,
        )
        instrument.notes.append(
            pretty_midi.Note(velocity=n.velocity, pitch=n.pitch, start=n.start, end=end)
        )
        for offset, cents in n.pitch_bends:
            instrument.pitch_bends.append(
                pretty_midi.PitchBend(
                    pitch=cents_to_pitch_bend(cents),
                    time=n.start + offset,
                )
            )
        if n.pitch_offset_cents and not n.pitch_bends:
            instrument.pitch_bends.append(
                pretty_midi.PitchBend(
                    pitch=cents_to_pitch_bend(n.pitch_offset_cents),
                    time=n.start,
                )
            )
    pm.instruments.append(instrument)
    return pm


def write_midi(
    notes: list[TimedNote],
    output_path: Path,
    *,
    program: int = 40,
    legato_overlap: float = 0.0,
    legato_overlaps: list[float] | None = None,
) -> Path:
    """Write timed notes to a MIDI file (violin default, GM program 40)."""
    pm = notes_to_pretty_midi(
        notes,
        program=program,
        legato_overlap=legato_overlap,
        legato_overlaps=legato_overlaps,
    )
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pm.write(str(output_path))
    return output_path


def render_notation_to_midi(
    notation: str,
    output_path: Path,
    *,
    raga_name: str = "charukeshi",
    tempo_bpm: float = 60.0,
    beats_per_note: float = 0.5,
    hold_beats: float = 0.5,
    ragas_dir: Path | None = None,
    apply_gamaka_rules: bool = False,
    tonic_midi: int | None = None,
    program: int = 40,
    legato_overlap: float = 0.0,
) -> Path:
    """Parse notation and write a MIDI file."""
    from swarasynth.parser import parse_notation

    events = parse_notation(notation)
    notes = events_to_timed_notes(
        events,
        raga_name,
        beats_per_note=beats_per_note,
        hold_beats=hold_beats,
        tempo_bpm=tempo_bpm,
        ragas_dir=ragas_dir,
        apply_gamaka_rules=apply_gamaka_rules,
        tonic_midi=tonic_midi,
    )
    return write_midi(notes, output_path, program=program, legato_overlap=legato_overlap)
