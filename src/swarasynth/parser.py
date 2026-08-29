"""Parse plain-text swara notation into events."""

from __future__ import annotations

import re

from swarasynth.models import EventKind, ParsedEvent, SwaraToken

# Carnatic swara names with optional octave markers attached.
_SWARA_RE = re.compile(
    r"^(?P<name>[SRGMPND](?:1|2|3)?)(?P<octave>['.])?$",
    re.IGNORECASE,
)


def parse_notation(text: str) -> list[ParsedEvent]:
    """Parse notation string into note and hold events.

    Examples:
        "P , D1 P M1 G3 , M1 R2 S ,"
        "S R2 G3 M1 P D1 N2 S'"
    """
    events: list[ParsedEvent] = []
    for raw in text.replace("\n", " ").split():
        token = raw.strip()
        if not token:
            continue
        if token == ",":
            events.append(ParsedEvent(kind=EventKind.HOLD))
            continue
        swara = _parse_swara_token(token)
        events.append(ParsedEvent(kind=EventKind.NOTE, swara=swara))
    return events


def _parse_swara_token(token: str) -> SwaraToken:
    # Leading dot octave: .S
    if token.startswith(".") and len(token) > 1:
        inner = _parse_swara_token(token[1:])
        return SwaraToken(name=inner.name, octave_shift=inner.octave_shift - 1)

    m = _SWARA_RE.match(token)
    if not m:
        raise ValueError(f"Unrecognized swara token: {token!r}")

    name = m.group("name").upper()
    # S (shadjam) and P (panchamam) have no variants; R/G/M/D/N need 1/2/3.
    if len(name) == 1 and name not in ("S", "P"):
        raise ValueError(f"Ambiguous swara (need variant number): {token!r}")

    octave_shift = 0
    oct_mark = m.group("octave")
    if oct_mark == "'":
        octave_shift = 1
    elif oct_mark == ".":
        octave_shift = -1

    return SwaraToken(name=name, octave_shift=octave_shift)
