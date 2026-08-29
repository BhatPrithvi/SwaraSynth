"""Practice session: section playback with tala, tanpura, and looping."""

from __future__ import annotations

from pathlib import Path

from swarasynth.articulation import apply_syllable_articulation, expand_legato_overlaps
from swarasynth.audio import (
    PRACTICE_LEGATO_OVERLAP,
    loop_notes,
    midi_to_hz,
    mix_buffers,
    render_clicks,
    render_instrument_melody,
    render_tanpura,
    write_wav,
)
from swarasynth.midi_writer import write_midi
from swarasynth.models import TimedNote
from swarasynth.parser import parse_notation
from swarasynth.pieces import PIECES_DIR, Piece, load_piece
from swarasynth.tala import events_to_timed_notes_tala, misra_chapu_clicks
from swarasynth.tuning import parse_tonic


def schedule_section(
    piece: Piece,
    section_name: str,
    *,
    tonic_midi: int | None = None,
    apply_gamaka: bool | None = None,
    ragas_dir: Path | None = None,
    pieces_dir: Path | None = None,
) -> list[TimedNote]:
    notation = piece.load_section_notation(section_name)
    events = parse_notation(notation)
    tonic = tonic_midi
    if tonic is None:
        tonic = parse_tonic(piece.tonic_default)

    ps = piece.practice
    use_gamaka = ps.gamaka if apply_gamaka is None else apply_gamaka
    apm = ps.aksharams_per_minute if ps.aksharams_per_minute is not None else piece.aksharams_per_minute

    return events_to_timed_notes_tala(
        events,
        piece.raga,
        tala=piece.tala,
        aksharams_per_minute=apm,
        hold_aksharams=ps.hold_aksharams,
        opening_hold_aksharams=ps.opening_hold_aksharams,
        comma_hold_aksharams=ps.comma_hold_aksharams,
        ragas_dir=ragas_dir,
        apply_gamaka_rules=use_gamaka,
        tonic_midi=tonic,
        gamaka_depth=ps.gamaka_depth,
        connecting_jarus=use_gamaka and (ps.connecting_jarus or apply_gamaka is True),
        apply_shruti=ps.apply_shruti if not use_gamaka else True,
        syllable_rhythm=ps.syllable_rhythm,
        piece_id=piece.id,
        section=section_name,
        pieces_dir=pieces_dir or PIECES_DIR,
    )


def _articulate_section(
    piece: Piece,
    section_name: str,
    notes: list[TimedNote],
    *,
    pieces_dir: Path | None = None,
) -> tuple[list[TimedNote], list[float] | None]:
    ps = piece.practice
    if not (ps.syllable_rhythm and ps.syllable_articulation):
        return notes, None
    return apply_syllable_articulation(
        notes,
        piece_id=piece.id,
        section=section_name,
        pieces_dir=pieces_dir or PIECES_DIR,
        gap_sec=ps.group_gap_ms / 1000.0,
    )


def _offset_notes(notes: list[TimedNote], offset: float) -> list[TimedNote]:
    if offset == 0.0:
        return list(notes)
    return [
        TimedNote(
            pitch=n.pitch,
            start=n.start + offset,
            duration=n.duration,
            velocity=n.velocity,
            pitch_offset_cents=n.pitch_offset_cents,
            pitch_bends=tuple((t + offset, c) for t, c in n.pitch_bends),
        )
        for n in notes
    ]


def schedule_piece(
    piece: Piece,
    *,
    section: str | None = None,
    tonic_midi: int | None = None,
    apply_gamaka: bool | None = None,
    ragas_dir: Path | None = None,
    pieces_dir: Path | None = None,
    section_gap_sec: float = 1.2,
) -> tuple[list[TimedNote], list[float] | None]:
    """Schedule one section, or all sections when section is None/'all'/'full'."""
    names = (
        [s.name for s in piece.sections]
        if section is None or section in ("all", "full")
        else [section]
    )
    all_notes: list[TimedNote] = []
    all_overlaps: list[float] = []
    use_overlaps = True
    cursor = 0.0
    for i, name in enumerate(names):
        notes = schedule_section(
            piece,
            name,
            tonic_midi=tonic_midi,
            apply_gamaka=apply_gamaka,
            ragas_dir=ragas_dir,
            pieces_dir=pieces_dir,
        )
        notes, overlaps = _articulate_section(piece, name, notes, pieces_dir=pieces_dir)
        if overlaps is None:
            use_overlaps = False
        elif use_overlaps:
            all_overlaps.extend(overlaps)
        all_notes.extend(_offset_notes(notes, cursor))
        if notes:
            end = max(n.start + n.duration for n in notes)
            cursor += end + (section_gap_sec if i + 1 < len(names) else 0.0)
    return all_notes, (all_overlaps if use_overlaps and all_notes else None)


def run_practice(
    piece_id: str,
    output_path: Path,
    *,
    section: str | None = None,
    loops: int = 2,
    tonic: str | None = None,
    apply_gamaka: bool | None = None,
    instrument_program: int | None = None,
    tala_clicks: bool = True,
    tanpura: bool = True,
    also_midi: bool = False,
    pieces_dir: Path | None = None,
    ragas_dir: Path | None = None,
) -> Path:
    piece = load_piece(piece_id, pieces_dir)
    # Default remains first section; use --section all for the full kriti.
    sec_arg = section if section is not None else piece.sections[0].name
    tonic_midi = parse_tonic(tonic) if tonic else parse_tonic(piece.tonic_default)
    ps = piece.practice
    program = instrument_program if instrument_program is not None else ps.instrument_program
    # Piano tutor: clear attacks. Violin expressive: very light legato (avoids bend clashes).
    legato = 0.0 if program == 0 else 0.04

    notes, legato_overlaps = schedule_piece(
        piece,
        section=sec_arg,
        tonic_midi=tonic_midi,
        apply_gamaka=apply_gamaka,
        ragas_dir=ragas_dir,
        pieces_dir=pieces_dir,
    )
    if program == 0 and legato_overlaps is not None:
        legato_overlaps = [0.0] * len(legato_overlaps)
    notes_per_loop = len(notes)
    notes = loop_notes(notes, loops)
    if legato_overlaps is not None and loops > 1:
        legato_overlaps = expand_legato_overlaps(legato_overlaps, notes_per_loop, loops)

    if also_midi:
        midi_path = output_path.with_suffix(".mid")
        write_midi(
            notes,
            midi_path,
            program=program,
            legato_overlap=legato,
            legato_overlaps=legato_overlaps,
        )

    duration = max(n.start + n.duration for n in notes) if notes else 0.0
    melody_buf, _ = render_instrument_melody(
        notes,
        program=program,
        legato_overlap=legato,
        legato_overlaps=legato_overlaps,
    )
    buffers = [melody_buf]

    apm = piece.practice.aksharams_per_minute or piece.aksharams_per_minute

    if tanpura:
        buffers.append(render_tanpura(duration + 0.5, midi_to_hz(tonic_midi)))

    if tala_clicks and piece.tala == "misra_chapu":
        clicks = misra_chapu_clicks(duration, aksharams_per_minute=apm)
        buffers.append(render_clicks(clicks, duration))

    mixed = mix_buffers(*buffers)
    return write_wav(output_path, mixed)
