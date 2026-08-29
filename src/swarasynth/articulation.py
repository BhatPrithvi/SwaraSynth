"""Syllable-group articulation: gaps, accents, and selective legato."""

from __future__ import annotations

from swarasynth.models import TimedNote
from swarasynth.syllable_rhythm import SyllableGroup, align_groups, load_section_rhythm


def group_start_indices(groups: tuple[SyllableGroup, ...]) -> tuple[int, ...]:
    """Note indices where each syllable group begins (always includes 0)."""
    starts = [0]
    idx = 0
    for group in groups:
        idx += group.note_count
        starts.append(idx)
    return tuple(starts[:-1])


def legato_overlaps_for_notes(
    notes: list[TimedNote],
    group_starts: tuple[int, ...],
    *,
    full_overlap: float = 0.12,
    light_overlap: float = 0.05,
    short_note_sec: float = 0.42,
) -> list[float]:
    """Per-pair legato overlap from note i into note i+1 (group boundaries = 0)."""
    boundary_starts = set(group_starts) - {0}
    overlaps: list[float] = []
    for i in range(len(notes) - 1):
        if (i + 1) in boundary_starts:
            if notes[i].pitch == notes[i + 1].pitch:
                overlaps.append(light_overlap)
            else:
                overlaps.append(0.0)
            continue
        min_dur = min(notes[i].duration, notes[i + 1].duration)
        if min_dur < short_note_sec:
            overlaps.append(light_overlap)
        else:
            overlaps.append(full_overlap)
    return overlaps


def apply_group_articulation(
    notes: list[TimedNote],
    group_starts: tuple[int, ...],
    *,
    gap_sec: float = 0.055,
    accent_velocity: int = 92,
    passing_velocity: int = 70,
    sustain_velocity: int = 84,
    short_note_sec: float = 0.42,
) -> list[TimedNote]:
    """Insert micro-gaps at group boundaries and accent group openings.

    Same-pitch group boundaries (e.g. M|m of pm|mggr) get a half-gap and a
    mild accent so fast runs still read clearly. Repeated pitches inside a
    group (G G) get a slight re-attack so they do not fuse.
    """
    if not notes:
        return []

    gap_starts = set(group_starts) - {0}
    out: list[TimedNote] = []
    extra_delay = 0.0

    for i, note in enumerate(notes):
        same_pitch_boundary = False
        if i in gap_starts and out:
            same_pitch_boundary = out[-1].pitch == note.pitch

        if i in gap_starts:
            gap = gap_sec * 0.5 if same_pitch_boundary else gap_sec
            extra_delay += gap
            if out:
                prev = out[-1]
                shorten = min(gap * 0.4, prev.duration * 0.12)
                if shorten > 0:
                    out[-1] = TimedNote(
                        pitch=prev.pitch,
                        start=prev.start,
                        duration=prev.duration - shorten,
                        velocity=prev.velocity,
                        pitch_offset_cents=prev.pitch_offset_cents,
                        pitch_bends=prev.pitch_bends,
                    )

        # Repeated pitch inside a run: tiny separation so G G / similar read as two
        if out and i not in gap_starts and out[-1].pitch == note.pitch and note.duration < short_note_sec:
            sep = min(0.018, note.duration * 0.08)
            if sep > 0:
                prev = out[-1]
                out[-1] = TimedNote(
                    pitch=prev.pitch,
                    start=prev.start,
                    duration=max(0.04, prev.duration - sep),
                    velocity=prev.velocity,
                    pitch_offset_cents=prev.pitch_offset_cents,
                    pitch_bends=prev.pitch_bends,
                )
                extra_delay += sep

        if i in group_starts:
            velocity = accent_velocity - 8 if same_pitch_boundary else accent_velocity
        elif out and out[-1].pitch == note.pitch and note.duration < short_note_sec:
            velocity = max(62, passing_velocity - 6)
        elif note.duration < short_note_sec:
            velocity = passing_velocity
        else:
            velocity = sustain_velocity

        out.append(
            TimedNote(
                pitch=note.pitch,
                start=note.start + extra_delay,
                duration=note.duration,
                velocity=velocity,
                pitch_offset_cents=note.pitch_offset_cents,
                pitch_bends=note.pitch_bends,
            )
        )

    return out


def expand_legato_overlaps(
    overlaps: list[float],
    notes_per_loop: int,
    loops: int,
) -> list[float]:
    """Repeat per-loop legato overlaps; no overlap across loop boundaries."""
    if loops <= 1:
        return overlaps
    expanded: list[float] = []
    for loop in range(loops):
        for i, overlap in enumerate(overlaps):
            at_loop_end = loop < loops - 1 and i == len(overlaps) - 1
            expanded.append(0.0 if at_loop_end else overlap)
    return expanded


def apply_syllable_articulation(
    notes: list[TimedNote],
    *,
    piece_id: str,
    section: str,
    pieces_dir,
    gap_sec: float = 0.055,
    full_legato_overlap: float = 0.12,
    light_legato_overlap: float = 0.05,
) -> tuple[list[TimedNote], list[float] | None]:
    """Apply syllable-group articulation when a rhythm profile exists."""
    groups = load_section_rhythm(piece_id, section, pieces_dir)
    if groups is None:
        return notes, None

    groups = align_groups(groups, len(notes))
    starts = group_start_indices(groups)
    articulated = apply_group_articulation(notes, starts, gap_sec=gap_sec)
    overlaps = legato_overlaps_for_notes(
        articulated,
        starts,
        full_overlap=full_legato_overlap,
        light_overlap=light_legato_overlap,
    )
    return articulated, overlaps
