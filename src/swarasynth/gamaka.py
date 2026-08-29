"""Apply raga gamaka rules as MIDI pitch-bend curves."""

from __future__ import annotations

from swarasynth.models import EventKind, ParsedEvent, SwaraToken, TimedNote
from swarasynth.tuning import swara_to_midi


def cents_to_pitch_bend(cents: float, bend_range_semitones: float = 2.0) -> int:
    """Convert cents to MIDI pitch-wheel units (±8192 for default ±2 semitone range)."""
    semitones = cents / 100.0
    value = int(round(semitones / bend_range_semitones * 8192))
    return max(-8192, min(8191, value))


def _note_swara_sequence(events: list[ParsedEvent]) -> list[SwaraToken]:
    return [ev.swara for ev in events if ev.kind == EventKind.NOTE and ev.swara is not None]


def _rule_matches(
    rule: dict,
    prev: SwaraToken | None,
    curr: SwaraToken,
    nxt: SwaraToken | None,
) -> bool:
    if rule.get("swara") != curr.name:
        return False
    when_prev = rule.get("when_prev")
    if when_prev is not None and (prev is None or prev.name != when_prev):
        return False
    when_next = rule.get("when_next")
    if when_next is not None and (nxt is None or nxt.name != when_next):
        return False
    return True


def _kampita_curve(
    duration: float,
    *,
    depth_cents: float,
    cycles: float,
) -> list[tuple[float, float]]:
    """Triangular oscillation around written pitch."""
    if duration <= 0 or depth_cents <= 0 or cycles <= 0:
        return []

    points: list[tuple[float, float]] = [(0.0, 0.0)]
    steps = max(4, int(cycles * 4))
    for i in range(1, steps + 1):
        t = duration * i / steps
        phase = (i / steps) * cycles * 2
        # Triangle wave in [-1, 1]
        frac = phase % 2
        wave = 1 - 2 * abs(frac - 1) if frac <= 1 else 2 * abs(frac - 1.5) - 1
        # Simpler triangle: alternate up/down
        wave = 1.0 if i % 2 else -1.0
        if i == steps:
            wave = 0.0
        points.append((t, wave * depth_cents))
    points.append((duration, 0.0))
    return points


def _jaru_in_curve(
    duration: float,
    *,
    depth_cents: float,
    portion: float,
    from_above: bool,
) -> list[tuple[float, float]]:
    """Slide into the written pitch from the previous swara direction."""
    if duration <= 0 or depth_cents <= 0:
        return []

    portion = max(0.05, min(1.0, portion))
    end_t = duration * portion
    start_cents = depth_cents if from_above else -depth_cents
    return [
        (0.0, start_cents),
        (end_t, 0.0),
        (duration, 0.0),
    ]


def _curve_for_rule(
    rule: dict,
    note: TimedNote,
    prev: SwaraToken | None,
    curr: SwaraToken,
    nxt: SwaraToken | None,
    raga: dict,
) -> list[tuple[float, float]]:
    gamaka_type = rule.get("type", "kampita")
    depth_cents = float(rule.get("depth_cents", 30))

    if gamaka_type == "kampita":
        return _kampita_curve(
            note.duration,
            depth_cents=depth_cents,
            cycles=float(rule.get("cycles", 1)),
        )

    if gamaka_type == "jaru_in":
        portion = float(rule.get("portion", 0.35))
        if prev is not None:
            prev_pitch = swara_to_midi(prev, raga)
            curr_pitch = swara_to_midi(curr, raga)
            from_above = prev_pitch > curr_pitch
        else:
            from_above = True
        depth_cents = min(depth_cents, 80.0)
        return _jaru_in_curve(
            note.duration,
            depth_cents=depth_cents,
            portion=portion,
            from_above=from_above,
        )

    if gamaka_type == "jaru_out" and nxt is not None:
        portion = float(rule.get("portion", 0.25))
        curr_pitch = swara_to_midi(curr, raga)
        next_pitch = swara_to_midi(nxt, raga)
        to_above = next_pitch > curr_pitch
        start_t = note.duration * (1.0 - portion)
        end_cents = depth_cents if to_above else -depth_cents
        return [
            (0.0, 0.0),
            (start_t, 0.0),
            (note.duration, end_cents),
        ]

    return []


def apply_gamakas(
    notes: list[TimedNote],
    events: list[ParsedEvent],
    raga: dict,
) -> list[TimedNote]:
    """Attach pitch-bend curves to timed notes using raga gamaka_rules."""
    rules: list[dict] = raga.get("gamaka_rules", [])
    if not rules or not notes:
        return notes

    swaras = _note_swara_sequence(events)
    if len(swaras) != len(notes):
        return notes

    enriched: list[TimedNote] = []
    for i, note in enumerate(notes):
        prev = swaras[i - 1] if i > 0 else None
        curr = swaras[i]
        nxt = swaras[i + 1] if i + 1 < len(swaras) else None

        bends: list[tuple[float, float]] = []
        for rule in rules:
            if _rule_matches(rule, prev, curr, nxt):
                bends = _curve_for_rule(rule, note, prev, curr, nxt, raga)
                break

        if bends:
            enriched.append(
                TimedNote(
                    pitch=note.pitch,
                    start=note.start,
                    duration=note.duration,
                    velocity=note.velocity,
                    pitch_bends=bends,
                )
            )
        else:
            enriched.append(note)

    return enriched
