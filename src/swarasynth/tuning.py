"""Raga tuning: swara names to MIDI pitch numbers."""

from __future__ import annotations

import json
import re
from pathlib import Path

from swarasynth.models import SwaraToken

_NOTE_RE = re.compile(
    r"^(?P<letter>[A-Ga-g])(?P<acc>(?:#|b|♯|♭)?)(?P<octave>\d)?$"
)

_LETTER_SEMITONES = {
    "C": 0,
    "D": 2,
    "E": 4,
    "F": 5,
    "G": 7,
    "A": 9,
    "B": 11,
}

# Default package-adjacent ragas directory
RAGAS_DIR = Path(__file__).resolve().parents[2] / "ragas"


def parse_tonic(value: str) -> int:
    """Parse a tonic as a MIDI note number or Western note name (e.g. C#, F#4, Eb3)."""
    text = value.strip()
    if not text:
        raise ValueError("Tonic cannot be empty")

    if text.isdigit() or (text.startswith("-") and text[1:].isdigit()):
        midi = int(text)
        if not 0 <= midi <= 127:
            raise ValueError(f"Tonic MIDI out of range (0-127): {midi}")
        return midi

    match = _NOTE_RE.match(text)
    if not match:
        raise ValueError(f"Invalid tonic note name: {value!r}")

    letter = match.group("letter").upper()
    semitone = _LETTER_SEMITONES[letter]
    acc = match.group("acc")
    if acc in ("#", "♯"):
        semitone += 1
    elif acc in ("b", "♭"):
        semitone -= 1

    octave = int(match.group("octave")) if match.group("octave") is not None else 4
    midi = (octave + 1) * 12 + semitone
    if not 0 <= midi <= 127:
        raise ValueError(f"Tonic {value!r} is outside MIDI range (0-127)")
    return midi


def load_raga(name: str, ragas_dir: Path | None = None) -> dict:
    path = (ragas_dir or RAGAS_DIR) / f"{name.lower()}.json"
    if not path.exists():
        raise FileNotFoundError(f"Raga profile not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def swara_to_midi(swara: SwaraToken, raga: dict, tonic_midi: int | None = None) -> int:
    """Map a swara token to MIDI note number using raga pitch map."""
    tonic = tonic_midi if tonic_midi is not None else int(raga.get("tonic_midi", 60))
    pitch_map: dict[str, int] = raga["pitch_map"]
    if swara.name not in pitch_map:
        raise KeyError(f"Swara {swara.name!r} not in raga {raga.get('name', '?')}")

    semitone = pitch_map[swara.name]
    octave_shift = swara.octave_shift
    # Middle octave S is at tonic; each octave is 12 semitones
    if swara.name == "S":
        base = tonic + 12 * octave_shift
    else:
        # Other swaras defined relative to middle S (tonic) in pitch_map
        base = tonic + semitone + 12 * octave_shift

    return int(base)


def swara_shruti_cents(swara: SwaraToken, raga: dict) -> float:
    """Return shruti deviation from 12-TET for this swara (cents)."""
    shruti: dict[str, float] = raga.get("shruti_cents", {})
    return float(shruti.get(swara.name, 0.0))
