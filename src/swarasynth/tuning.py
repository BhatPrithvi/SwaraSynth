"""Raga tuning: swara names to MIDI pitch numbers."""

from __future__ import annotations

import json
from pathlib import Path

from swarasynth.models import SwaraToken

# Default package-adjacent ragas directory
RAGAS_DIR = Path(__file__).resolve().parents[2] / "ragas"


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
