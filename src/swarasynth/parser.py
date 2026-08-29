"""Parse plain-text swara notation into events."""

from __future__ import annotations

import re

from swarasynth.models import EventKind, ParsedEvent, SwaraToken

# Carnatic swara names with optional octave markers attached.
_SWARA_RE = re.compile(
    r"^(?P<name>[SRGMPND](?:1|2|3)?)(?P<octave>['.])?$"
)

# Default variants for single-letter Shivkumar notation (Charukeshi-style).
_SINGLE_LETTER_VARIANT: dict[str, str] = {
    "R": "R2",
    "G": "G3",
    "M": "M1",
    "D": "D1",
    "N": "N2",
}


def parse_notation(text: str) -> list[ParsedEvent]:
    """Parse notation string into note and hold events.

    Shivkumar convention: lowercase letters = double speed (half duration).

    Examples:
        "P M m g g r S"
        "P , D1 P M1 G3 , M1 R2 S ,"
        "S ;"  # semicolon = double hold (Shivkumar-style)
    """
    events: list[ParsedEvent] = []
    for raw in text.replace("\n", " ").split():
        token = raw.strip()
        if not token:
            continue
        if token == ",":
            events.append(ParsedEvent(kind=EventKind.HOLD))
            continue
        if token == ";":
            events.append(ParsedEvent(kind=EventKind.HOLD))
            events.append(ParsedEvent(kind=EventKind.HOLD))
            continue
        swara = _parse_swara_token(token)
        events.append(ParsedEvent(kind=EventKind.NOTE, swara=swara))
    return events


def _swara_speed_from_token(token: str) -> float:
    """Shivkumar.org: lowercase swara letter = double speed."""
    for ch in token:
        if ch.isalpha():
            return 2.0 if ch.islower() else 1.0
    return 1.0


def _parse_swara_token(token: str) -> SwaraToken:
    # Leading dot octave: .S
    if token.startswith(".") and len(token) > 1:
        inner = _parse_swara_token(token[1:])
        return SwaraToken(
            name=inner.name,
            octave_shift=inner.octave_shift - 1,
            speed=inner.speed,
        )

    speed = _swara_speed_from_token(token)
    normalized = token
    if speed == 2.0:
        normalized = "".join(ch.upper() if ch.isalpha() else ch for ch in token)

    m = _SWARA_RE.match(normalized)
    if not m:
        raise ValueError(f"Unrecognized swara token: {token!r}")

    name = m.group("name").upper()
    if len(name) == 1 and name not in ("S", "P"):
        variant = _SINGLE_LETTER_VARIANT.get(name)
        if variant is None:
            raise ValueError(f"Ambiguous swara (need variant number): {token!r}")
        name = variant

    octave_shift = 0
    oct_mark = m.group("octave")
    if oct_mark == "'":
        octave_shift = 1
    elif oct_mark == ".":
        octave_shift = -1

    return SwaraToken(name=name, octave_shift=octave_shift, speed=speed)
