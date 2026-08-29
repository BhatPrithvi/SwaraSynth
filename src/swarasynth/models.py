"""Data models for SwaraSynth."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class EventKind(str, Enum):
    NOTE = "note"
    HOLD = "hold"


@dataclass(frozen=True)
class SwaraToken:
    """One parsed swara, e.g. G3 or S'."""

    name: str
    octave_shift: int = 0  # -1 lower (.), 0 middle, +1 upper (')


@dataclass(frozen=True)
class ParsedEvent:
    kind: EventKind
    swara: SwaraToken | None = None
    hold_beats: float = 0.5


@dataclass(frozen=True)
class TimedNote:
    """MIDI-ready note with start time and duration in seconds."""

    pitch: int
    start: float
    duration: float
    velocity: int = 90
