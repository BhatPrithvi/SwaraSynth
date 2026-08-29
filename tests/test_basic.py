from pathlib import Path

import pytest

from swarasynth.models import EventKind, SwaraToken
from swarasynth.parser import parse_notation
from swarasynth.tuning import load_raga, swara_to_midi
from swarasynth.midi_writer import events_to_timed_notes, render_notation_to_midi

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
RAGAS = Path(__file__).resolve().parents[1] / "ragas"


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


def test_invalid_token_raises():
    with pytest.raises(ValueError):
        parse_notation("X1")
