from pathlib import Path

import pytest

from swarasynth.articulation import (
    apply_group_articulation,
    apply_syllable_articulation,
    expand_legato_overlaps,
    group_start_indices,
    legato_overlaps_for_notes,
)
from swarasynth.gamaka import apply_gamakas
from swarasynth.models import TimedNote
from swarasynth.parser import parse_notation
from swarasynth.pieces import load_piece
from swarasynth.practice import schedule_section
from swarasynth.syllable_rhythm import SyllableGroup
from swarasynth.tala import events_to_timed_notes_tala

ROOT = Path(__file__).resolve().parents[1]
PIECES = ROOT / "pieces"
RAGAS = ROOT / "ragas"


def test_group_start_indices():
    groups = (SyllableGroup(2, 2), SyllableGroup(2, 4), SyllableGroup(2, 1))
    assert group_start_indices(groups) == (0, 2, 6)


def test_group_gap_delays_later_notes():
    notes = [
        TimedNote(pitch=71, start=0.0, duration=0.7),
        TimedNote(pitch=70, start=0.7, duration=0.7),
        TimedNote(pitch=69, start=1.4, duration=0.35),
        TimedNote(pitch=66, start=1.75, duration=0.35),
    ]
    out = apply_group_articulation(notes, (0, 2), gap_sec=0.05)
    assert out[2].start == pytest.approx(1.45)
    assert out[0].duration > out[2].duration


def test_legato_light_overlap_on_same_pitch_boundary():
    notes = [
        TimedNote(pitch=71, start=0.0, duration=0.7),
        TimedNote(pitch=70, start=0.7, duration=0.7),
        TimedNote(pitch=70, start=1.4, duration=0.35),
        TimedNote(pitch=69, start=1.75, duration=0.35),
    ]
    overlaps = legato_overlaps_for_notes(notes, (0, 2))
    assert overlaps[0] > 0
    assert overlaps[1] == 0.05
    assert overlaps[2] > 0


def test_same_pitch_group_boundary_half_gap():
    notes = [
        TimedNote(pitch=71, start=0.0, duration=0.7),
        TimedNote(pitch=70, start=0.7, duration=0.7),
        TimedNote(pitch=70, start=1.4, duration=0.35),
    ]
    raw = apply_group_articulation(notes, (0, 2), gap_sec=0.05)
    assert raw[2].start == pytest.approx(1.425)
    assert raw[2].velocity >= 80


def test_repeated_pitch_gets_separation():
    notes = [
        TimedNote(pitch=69, start=0.0, duration=0.35),
        TimedNote(pitch=69, start=0.35, duration=0.35),
    ]
    out = apply_group_articulation(notes, (0,), gap_sec=0.05)
    assert out[1].start > 0.35
    assert out[1].velocity < out[0].velocity


def test_legato_zero_at_group_boundary():
    notes = [
        TimedNote(pitch=71, start=0.0, duration=0.7),
        TimedNote(pitch=70, start=0.7, duration=0.7),
        TimedNote(pitch=69, start=1.4, duration=0.35),
        TimedNote(pitch=66, start=1.75, duration=0.35),
    ]
    overlaps = legato_overlaps_for_notes(notes, (0, 2))
    assert overlaps[0] > 0
    assert overlaps[1] == 0.0
    assert overlaps[2] > 0


def test_expand_legato_overlaps_for_loops():
    base = [0.12, 0.0, 0.05]
    expanded = expand_legato_overlaps(base, notes_per_loop=4, loops=2)
    assert len(expanded) == 6
    assert expanded[2] == 0.0


def test_pallavi_opening_articulation():
    piece = load_piece("krupaya_palaya", PIECES)
    line1 = piece.section("pallavi").notation_path.read_text().splitlines()[0]
    events = parse_notation(line1)
    notes = events_to_timed_notes_tala(
        events,
        "charukeshi",
        ragas_dir=RAGAS,
        aksharams_per_minute=60,
        hold_aksharams=0,
        syllable_rhythm=True,
        piece_id="krupaya_palaya",
        section="pallavi",
        pieces_dir=PIECES,
        apply_gamaka_rules=False,
    )
    articulated, overlaps = apply_syllable_articulation(
        notes,
        piece_id="krupaya_palaya",
        section="pallavi",
        pieces_dir=PIECES,
    )
    assert articulated[2].start > notes[2].start  # half-gap at pm|mggr (same pitch)
    assert overlaps is not None
    assert overlaps[1] == 0.05
    assert overlaps[5] == 0.0
    assert articulated[2].velocity >= 80  # mild accent on mggr start


def test_short_notes_get_lighter_gamaka():
    raga = __import__("swarasynth.tuning", fromlist=["load_raga"]).load_raga("charukeshi", RAGAS)
    events = parse_notation("G3 R2")
    long_note = TimedNote(pitch=69, start=0.0, duration=0.8)
    short_note = TimedNote(pitch=66, start=0.8, duration=0.3)
    out_long = apply_gamakas([long_note], events[:1], raga, depth_scale=1.0, connecting_jarus=True)
    out_short = apply_gamakas([short_note], events[1:], raga, depth_scale=1.0, connecting_jarus=True)
    long_motion = max(abs(c + 14.0) for _, c in out_long[0].pitch_bends) if out_long[0].pitch_bends else 0
    short_motion = max(abs(c + 22.0) for _, c in out_short[0].pitch_bends) if out_short[0].pitch_bends else 0
    assert len(out_long[0].pitch_bends) > len(out_short[0].pitch_bends)
    assert long_motion >= short_motion


def test_schedule_section_still_returns_notes_only():
    piece = load_piece("krupaya_palaya", PIECES)
    notes = schedule_section(piece, "pallavi", ragas_dir=RAGAS)
    assert isinstance(notes, list)
    assert len(notes) > 50
