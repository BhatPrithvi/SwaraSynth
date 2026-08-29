from pathlib import Path

import pretty_midi
import pytest

from swarasynth.models import EventKind, SwaraToken
from swarasynth.parser import parse_notation
from swarasynth.tuning import load_raga, parse_tonic, swara_to_midi
from swarasynth.midi_writer import events_to_timed_notes, render_notation_to_midi
from swarasynth.pieces import load_piece

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
RAGAS = Path(__file__).resolve().parents[1] / "ragas"
PIECES = Path(__file__).resolve().parents[1] / "pieces"


def test_parse_opening_phrase():
    text = (EXAMPLES / "krupaya_palaya_opening.txt").read_text()
    events = parse_notation(text)
    assert len(events) == 11
    assert events[0].kind == EventKind.NOTE
    assert events[0].swara is not None
    assert events[0].swara.name == "P"
    assert events[1].kind == EventKind.HOLD


def test_parse_octave_markers():
    events = parse_notation("S' .S S")
    assert events[0].swara.octave_shift == 1
    assert events[1].swara.octave_shift == -1
    assert events[2].swara.octave_shift == 0


def test_charukeshi_tuning():
    raga = load_raga("charukeshi", RAGAS)

    assert swara_to_midi(SwaraToken("S"), raga) == 60
    assert swara_to_midi(SwaraToken("R2"), raga) == 62
    assert swara_to_midi(SwaraToken("G3"), raga) == 65
    assert swara_to_midi(SwaraToken("M1"), raga) == 66
    assert swara_to_midi(SwaraToken("P"), raga) == 67
    assert swara_to_midi(SwaraToken("D1"), raga) == 69
    assert swara_to_midi(SwaraToken("N2"), raga) == 71
    assert swara_to_midi(SwaraToken("S", octave_shift=1), raga) == 72


def test_parse_tonic_note_names():
    assert parse_tonic("C") == 60
    assert parse_tonic("C#") == 61
    assert parse_tonic("c#") == 61
    assert parse_tonic("F#4") == 66
    assert parse_tonic("Eb3") == 51
    assert parse_tonic("61") == 61


def test_tonic_shifts_rendered_pitch(tmp_path):
    raga = load_raga("charukeshi", RAGAS)
    notes = events_to_timed_notes(
        parse_notation("S"),
        "charukeshi",
        ragas_dir=RAGAS,
        tonic_midi=parse_tonic("C#"),
    )
    assert notes[0].pitch == swara_to_midi(SwaraToken("S"), raga, tonic_midi=61)


def test_render_with_tonic_flag(tmp_path):
    text = "S"
    out = tmp_path / "tonic.mid"
    render_notation_to_midi(
        text,
        out,
        raga_name="charukeshi",
        ragas_dir=RAGAS,
        tonic_midi=parse_tonic("F#"),
    )
    assert out.exists()


def test_parse_semicolon_double_hold():
    events = parse_notation("S ;")
    assert len(events) == 3
    assert events[1].kind == EventKind.HOLD
    assert events[2].kind == EventKind.HOLD


def test_lowercase_swara_is_double_speed():
    events = parse_notation("P M m g r")
    assert events[0].swara.name == "P"
    assert events[0].swara.speed == 1.0
    assert events[1].swara.name == "M1"
    assert events[1].swara.speed == 1.0
    assert events[2].swara.name == "M1"
    assert events[2].swara.speed == 2.0
    assert events[3].swara.name == "G3"
    assert events[3].swara.speed == 2.0
    assert events[4].swara.name == "R2"
    assert events[4].swara.speed == 2.0


def test_explicit_variant_still_parses():
    events = parse_notation("M1 G3 R2")
    assert [e.swara.name for e in events] == ["M1", "G3", "R2"]
    assert all(e.swara.speed == 1.0 for e in events)


def test_semicolon_extends_more_than_comma():
    comma = events_to_timed_notes(
        parse_notation("P ,"), "charukeshi", ragas_dir=RAGAS, tempo_bpm=60.0, hold_beats=1.0
    )
    semi = events_to_timed_notes(
        parse_notation("P ;"), "charukeshi", ragas_dir=RAGAS, tempo_bpm=60.0, hold_beats=1.0
    )
    assert semi[0].duration > comma[0].duration


def test_hold_extends_previous_note():
    events = parse_notation("P , D1")
    notes = events_to_timed_notes(events, "charukeshi", ragas_dir=RAGAS, tempo_bpm=60.0)
    assert len(notes) == 2
    assert notes[0].duration > notes[1].duration


def test_render_midi_file(tmp_path):
    text = "S R2 G3 M1 P"
    out = tmp_path / "test.mid"
    render_notation_to_midi(text, out, raga_name="charukeshi", ragas_dir=RAGAS)
    assert out.exists()
    assert out.stat().st_size > 0


def test_default_instrument_is_violin(tmp_path):
    out = tmp_path / "violin.mid"
    render_notation_to_midi("S", out, raga_name="charukeshi", ragas_dir=RAGAS, apply_gamaka_rules=False)
    pm = pretty_midi.PrettyMIDI(str(out))
    assert pm.instruments[0].program == 40


def test_passing_swara_not_extended_by_following_comma():
    """Commas after passing swaras (R2 ,) add unwanted sustain."""
    good = events_to_timed_notes(
        parse_notation("S' , R2 G3'"), "charukeshi", ragas_dir=RAGAS, tempo_bpm=60.0, hold_beats=1.0
    )
    bad = events_to_timed_notes(
        parse_notation("S' , R2 , G3'"), "charukeshi", ragas_dir=RAGAS, tempo_bpm=60.0, hold_beats=1.0
    )
    assert good[1].duration < bad[1].duration
    assert good[0].duration == bad[0].duration


def test_pallavi_uses_tara_sa_before_hold():
    line = parse_notation("M1 G3 G3 R2 S' , R2")[4]
    assert line.swara is not None
    assert line.swara.name == "S"
    assert line.swara.octave_shift == 1


def test_pallavi_line1_opening_sa_is_madhya():
    piece = load_piece("krupaya_palaya", PIECES)
    text = piece.section("pallavi").notation_path.read_text(encoding="utf-8").splitlines()[0]
    events = [e for e in parse_notation(text) if e.swara]
    opening_sa = [e for e in events if e.swara and e.swara.name == "S"][0]
    assert opening_sa.swara.octave_shift == 0


def test_pallavi_ni_sa_ascent_uses_tara():
    """After madhya Ni, Sa (and Ri) in ascent are tara."""
    piece = load_piece("krupaya_palaya", PIECES)
    line3 = piece.section("pallavi").notation_path.read_text().splitlines()[2]
    line4 = piece.section("pallavi").notation_path.read_text().splitlines()[3]
    n3 = [e.swara for e in parse_notation(line3) if e.swara]
    n4 = [e.swara for e in parse_notation(line4) if e.swara]
    # ... n s' n ...
    assert n3[12].name == "N2" and n3[12].octave_shift == 0
    assert n3[13].name == "S" and n3[13].octave_shift == 1
    # ... n s' r' s' n ...
    assert n4[12].name == "N2" and n4[12].octave_shift == 0
    assert n4[13].name == "S" and n4[13].octave_shift == 1
    assert n4[14].name == "R2" and n4[14].octave_shift == 1
    assert n4[15].name == "S" and n4[15].octave_shift == 1
    assert n4[16].name == "N2" and n4[16].octave_shift == 0


def test_parse_lowercase_tara():
    events = parse_notation("n s' r'")
    assert events[0].swara.speed == 2.0 and events[0].swara.octave_shift == 0
    assert events[1].swara.name == "S" and events[1].swara.octave_shift == 1
    assert events[2].swara.name == "R2" and events[2].swara.octave_shift == 1


def test_invalid_token_raises():
    with pytest.raises(ValueError):
        parse_notation("X1")
