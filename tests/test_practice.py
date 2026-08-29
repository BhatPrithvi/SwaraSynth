from pathlib import Path

import pytest

from swarasynth.audio import find_soundfont, loop_notes, render_instrument_melody, write_wav
from swarasynth.models import TimedNote
from swarasynth.parser import parse_notation
from swarasynth.pieces import load_piece
from swarasynth.practice import run_practice, schedule_section
from swarasynth.tala import events_to_timed_notes_tala

ROOT = Path(__file__).resolve().parents[1]
PIECES = ROOT / "pieces"
RAGAS = ROOT / "ragas"


def test_load_krupaya_piece():
    piece = load_piece("krupaya_palaya", PIECES)
    assert piece.raga == "charukeshi"
    assert piece.tala == "misra_chapu"
    assert len(piece.sections) == 6
    assert piece.section("pallavi").notation_path.exists()


def test_pallavi_opening_syllable_groups():
    """pm(2) mggr(2) S(2) — not equal length per swara."""
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
    )
    # P, M1: 1 aksharam each at 60 apm = 1.0s
    assert notes[0].duration == pytest.approx(1.0)
    assert notes[1].duration == pytest.approx(1.0)
    # M1, G3, G3, R2: 2 aksharams / 4 = 0.5s each
    assert notes[2].duration == pytest.approx(0.5)
    assert notes[5].duration == pytest.approx(0.5)
    # S (madhya): 1 aksharam + comma hold when enabled
    assert notes[6].duration == pytest.approx(1.0)


def test_pallavi_tail_mixed_case_speeds():
    """p d p d M P: lowercase half duration of uppercase within same group."""
    from swarasynth.syllable_rhythm import SyllableGroup, group_durations, note_speeds_from_events

    events = parse_notation("p d p d M P")
    speeds = note_speeds_from_events(events)
    durs = group_durations((SyllableGroup(3, 6),), sec_per_aksharam=1.0, speeds=speeds)
    assert durs[0] == pytest.approx(0.375)
    assert durs[4] == pytest.approx(0.75)
    assert durs[4] == pytest.approx(durs[0] * 2)


def test_tala_sustained_note_longer_than_passing():
    good = events_to_timed_notes_tala(
        parse_notation("S' , R2 G3'"),
        "charukeshi",
        ragas_dir=RAGAS,
        aksharams_per_minute=120,
    )
    assert good[0].duration > good[1].duration


def test_schedule_pallavi_section():
    piece = load_piece("krupaya_palaya", PIECES)
    notes = schedule_section(piece, "pallavi", ragas_dir=RAGAS)
    assert len(notes) > 50
    assert max(n.start + n.duration for n in notes) < 150


def test_loop_notes():
    notes = [TimedNote(pitch=60, start=0.0, duration=1.0)]
    out = loop_notes(notes, 3, gap_sec=0.5)
    assert len(out) == 3
    assert out[1].start == pytest.approx(1.5)


def test_practice_writes_wav(tmp_path):
    out = run_practice(
        "krupaya_palaya",
        tmp_path / "p.wav",
        section="pallavi",
        loops=1,
        pieces_dir=PIECES,
        ragas_dir=RAGAS,
        tala_clicks=False,
    )
    assert out.exists()
    assert out.stat().st_size > 1000


def test_schedule_full_piece_concatenates_sections():
    from swarasynth.practice import schedule_piece

    piece = load_piece("krupaya_palaya", PIECES)
    notes, _ = schedule_piece(piece, section="all", ragas_dir=RAGAS, pieces_dir=PIECES)
    pallavi = schedule_section(piece, "pallavi", ragas_dir=RAGAS, pieces_dir=PIECES)
    assert len(notes) > len(pallavi)
    assert max(n.start + n.duration for n in notes) > 180


def test_all_sections_rhythm_matches_notation():
    from swarasynth.models import EventKind
    from swarasynth.parser import parse_notation
    from swarasynth.syllable_rhythm import load_section_rhythm, validate_rhythm

    piece = load_piece("krupaya_palaya", PIECES)
    for sec in piece.sections:
        text = piece.load_section_notation(sec.name)
        note_count = sum(1 for e in parse_notation(text) if e.kind == EventKind.NOTE)
        groups = load_section_rhythm("krupaya_palaya", sec.name, PIECES)
        validate_rhythm(groups, note_count, section=sec.name)


def test_karuna_kalusha_use_shivkumar_case_speed():
    from swarasynth.models import EventKind
    from swarasynth.parser import parse_notation

    piece = load_piece("krupaya_palaya", PIECES)
    for name in ("karuna", "kalusha", "paahi"):
        text = piece.load_section_notation(name)
        events = [e for e in parse_notation(text) if e.kind == EventKind.NOTE]
        fast = sum(1 for e in events if e.swara and e.swara.speed > 1.0)
        assert fast > 0, name


def test_kalusha_madhya_sa_and_tara_ni_ascent():
    from swarasynth.models import EventKind
    from swarasynth.parser import parse_notation

    piece = load_piece("krupaya_palaya", PIECES)
    notes = [e.swara for e in parse_notation(piece.load_section_notation("kalusha")) if e.kind == EventKind.NOTE]
    names = [s.name for s in notes]
    idx = names.index("S")
    assert notes[idx].octave_shift == 0  # madhya Sa after mggr
    assert names[-1] == "S" and notes[-1].octave_shift == 1  # tara Sa after Ni


def test_paahi_is_two_avartans():
    piece = load_piece("krupaya_palaya", PIECES)
    notes = schedule_section(piece, "paahi", ragas_dir=RAGAS, pieces_dir=PIECES)
    apm = piece.practice.aksharams_per_minute
    dur = max(n.start + n.duration for n in notes)
    aks = dur * apm / 60.0
    assert aks == pytest.approx(14.0, abs=0.05)


def test_write_wav(tmp_path):
    buf = [0.0, 0.5, -0.5, 0.0] * 100
    path = write_wav(tmp_path / "t.wav", buf)
    assert path.exists()


def test_find_soundfont():
    assert find_soundfont().is_file()


def test_pallavi_lines_are_two_avartans():
    """Each pallavi line ≈ 14 aks (2× Misra Chapu) including comma holds."""
    piece = load_piece("krupaya_palaya", PIECES)
    text = piece.section("pallavi").notation_path.read_text()
    events = parse_notation(text)
    notes = events_to_timed_notes_tala(
        events,
        "charukeshi",
        ragas_dir=RAGAS,
        aksharams_per_minute=60,
        hold_aksharams=1.0,
        opening_hold_aksharams=1.0,
        comma_hold_aksharams=1.0,
        syllable_rhythm=True,
        piece_id="krupaya_palaya",
        section="pallavi",
        pieces_dir=PIECES,
        apply_gamaka_rules=False,
    )
    # 60 apm → 1 aks = 1s. Line note counts: 16,18,18,18
    bounds = [0, 16, 34, 52, 70]
    for i in range(4):
        a, b = bounds[i], bounds[i + 1]
        dur = notes[b - 1].start + notes[b - 1].duration - notes[a].start
        assert dur == pytest.approx(14.0, abs=0.05), f"line {i+1} was {dur}"


def test_tutor_defaults_no_gamaka_piano():
    piece = load_piece("krupaya_palaya", PIECES)
    assert piece.practice.gamaka is False
    assert piece.practice.instrument_program == 0
    notes = schedule_section(piece, "pallavi", ragas_dir=RAGAS)
    assert all(not n.pitch_bends for n in notes)


def test_violin_melody_renders():
    notes = [
        TimedNote(pitch=64, start=0.0, duration=0.6),
        TimedNote(pitch=66, start=0.5, duration=0.6),
    ]
    buf, end = render_instrument_melody(notes, program=0)
    assert end == pytest.approx(1.1)
    assert len(buf) > 1000
    assert max(abs(v) for v in buf) > 0.01
