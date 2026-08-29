from pathlib import Path

import pretty_midi
import pytest

from swarasynth.gamaka import apply_gamakas, cents_to_pitch_bend
from swarasynth.models import EventKind, ParsedEvent, SwaraToken, TimedNote
from swarasynth.parser import parse_notation
from swarasynth.tuning import load_raga
from swarasynth.midi_writer import events_to_timed_notes, render_notation_to_midi

RAGAS = Path(__file__).resolve().parents[1] / "ragas"
EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


def test_cents_to_pitch_bend():
    assert cents_to_pitch_bend(0) == 0
    assert cents_to_pitch_bend(100) == 4096
    assert cents_to_pitch_bend(-50) == -2048


def test_gamaka_rules_add_pitch_bends():
    raga = load_raga("charukeshi", RAGAS)
    events = parse_notation("P , D1")
    notes = events_to_timed_notes(events, "charukeshi", ragas_dir=RAGAS, tempo_bpm=60.0)
    assert notes[0].pitch_bends


def test_m1_r2_s_descent_gets_jaru():
    raga = load_raga("charukeshi", RAGAS)
    events = parse_notation("M1 R2 S")
    notes = events_to_timed_notes(events, "charukeshi", ragas_dir=RAGAS, tempo_bpm=60.0)
    r2_note = notes[1]
    assert r2_note.pitch_bends
    assert r2_note.pitch_bends[0][1] > 0  # jaru_in from above after M1


def test_no_gamaka_leaves_notes_plain():
    events = parse_notation("G3 M1 R2")
    notes = events_to_timed_notes(
        events, "charukeshi", ragas_dir=RAGAS, apply_gamaka_rules=False
    )
    assert all(not n.pitch_bends for n in notes)


def test_apply_gamakas_matches_context():
    raga = load_raga("charukeshi", RAGAS)
    events = [
        ParsedEvent(kind=EventKind.NOTE, swara=SwaraToken("M1")),
        ParsedEvent(kind=EventKind.NOTE, swara=SwaraToken("R2")),
        ParsedEvent(kind=EventKind.NOTE, swara=SwaraToken("S")),
    ]
    notes = [
        TimedNote(pitch=66, start=0.0, duration=0.5),
        TimedNote(pitch=62, start=0.5, duration=0.5),
        TimedNote(pitch=60, start=1.0, duration=0.5),
    ]
    out = apply_gamakas(notes, events, raga)
    assert out[0].pitch_bends  # jaru_out on M1 before R2
    assert out[1].pitch_bends  # jaru_in on R2
    assert out[2].pitch_bends  # kampita on S after R2


def test_render_midi_includes_pitch_bend_events(tmp_path):
    text = (EXAMPLES / "krupaya_palaya_opening.txt").read_text()
    out = tmp_path / "gamaka.mid"
    render_notation_to_midi(text, out, raga_name="charukeshi", ragas_dir=RAGAS)
    pm = pretty_midi.PrettyMIDI(str(out))
    bends = pm.instruments[0].pitch_bends
    assert len(bends) > 0


def test_render_no_gamaka_has_no_pitch_bends(tmp_path):
    out = tmp_path / "plain.mid"
    render_notation_to_midi(
        "G3 M1 R2 S",
        out,
        raga_name="charukeshi",
        ragas_dir=RAGAS,
        apply_gamaka_rules=False,
    )
    pm = pretty_midi.PrettyMIDI(str(out))
    assert len(pm.instruments[0].pitch_bends) == 0
