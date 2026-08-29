"""Apply raga gamaka rules as MIDI pitch-bend curves.

Carnatic identity comes from continuous jarus (slides from the previous
swara) and kampita (oscillation around jeeva swaras), not tiny vibrato.
"""

from __future__ import annotations

import math

from swarasynth.models import EventKind, ParsedEvent, SwaraToken, TimedNote
from swarasynth.tuning import swara_shruti_cents, swara_to_midi

# Default GM pitch-bend range (±2 semitones). Keep headroom under 200¢.
_MAX_BEND_CENTS = 180.0

# Duration gates — fast syllable groups stay clean; long notes carry motion.
_MIN_JARU_DURATION = 0.40
_MIN_KAMPITA_DURATION = 0.50
_MIN_SUSTAIN_KAMPITA = 0.65

# Charukeshi / general Carnatic: these swaras carry the raga's life.
_JEEVA_DEFAULT = frozenset({"G3", "N2", "D1", "R2"})


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


def _clamp_cents(cents: float, max_cents: float = _MAX_BEND_CENTS) -> float:
    return max(-max_cents, min(max_cents, cents))


def _shruti_bend(swara: SwaraToken, raga: dict) -> float:
    return swara_shruti_cents(swara, raga)


def _approach_bend_cents(
    prev: SwaraToken,
    curr: SwaraToken,
    raga: dict,
    *,
    tonic_midi: int | None = None,
    max_cents: float = _MAX_BEND_CENTS,
) -> float:
    """Pitch-bend cents at note onset to match previous swara's effective pitch."""
    prev_midi = swara_to_midi(prev, raga, tonic_midi=tonic_midi)
    curr_midi = swara_to_midi(curr, raga, tonic_midi=tonic_midi)
    return _clamp_cents(
        (prev_midi - curr_midi) * 100.0 + _shruti_bend(prev, raga),
        max_cents,
    )


def _departure_bend_cents(
    curr: SwaraToken,
    nxt: SwaraToken,
    raga: dict,
    *,
    tonic_midi: int | None = None,
    strength: float = 0.55,
    max_cents: float = _MAX_BEND_CENTS,
) -> float:
    """Pitch-bend cents at note end leaning toward the next swara."""
    curr_midi = swara_to_midi(curr, raga, tonic_midi=tonic_midi)
    next_midi = swara_to_midi(nxt, raga, tonic_midi=tonic_midi)
    rest = _shruti_bend(curr, raga)
    lean = (next_midi - curr_midi) * 100.0 * strength
    return _clamp_cents(rest + lean, max_cents)


def _kampita_curve(
    duration: float,
    *,
    depth_cents: float,
    cycles: float,
    base_cents: float = 0.0,
) -> list[tuple[float, float]]:
    """Oscillation around base pitch (kampita)."""
    if duration <= 0 or depth_cents <= 0 or cycles <= 0:
        return []

    points: list[tuple[float, float]] = [(0.0, base_cents)]
    steps = max(8, int(cycles * 8))
    for i in range(1, steps + 1):
        t = duration * i / steps
        wave = math.sin(2 * math.pi * cycles * i / steps)
        if i == steps:
            wave = 0.0
        points.append((t, base_cents + wave * depth_cents))
    points.append((duration, base_cents))
    return points


def _jaru_in_curve(
    duration: float,
    *,
    start_cents: float,
    rest_cents: float,
    portion: float = 0.45,
) -> list[tuple[float, float]]:
    """Slide from start_cents into the swara's resting (shruti) pitch."""
    if duration <= 0:
        return []
    if abs(start_cents - rest_cents) < 10.0:
        return [(0.0, rest_cents), (duration, rest_cents)]

    portion = max(0.15, min(0.75, portion))
    end_t = duration * portion
    mid_t = end_t * 0.65
    mid_cents = start_cents * 0.25 + rest_cents * 0.75
    return [
        (0.0, start_cents),
        (mid_t, mid_cents),
        (end_t, rest_cents),
        (duration, rest_cents),
    ]


def _jaru_out_curve(
    duration: float,
    *,
    rest_cents: float,
    end_cents: float,
    portion: float = 0.35,
) -> list[tuple[float, float]]:
    """Leave resting pitch toward the next swara."""
    if duration <= 0:
        return []
    if abs(end_cents - rest_cents) < 10.0:
        return [(0.0, rest_cents), (duration, rest_cents)]

    portion = max(0.12, min(0.55, portion))
    start_t = duration * (1.0 - portion)
    return [
        (0.0, rest_cents),
        (start_t, rest_cents),
        (duration, end_cents),
    ]


def _jaru_in_legacy(
    duration: float,
    *,
    depth_cents: float,
    portion: float,
    from_above: bool,
    rest_cents: float,
) -> list[tuple[float, float]]:
    if duration <= 0 or depth_cents <= 0:
        return []
    start = rest_cents + (depth_cents if from_above else -depth_cents)
    return _jaru_in_curve(duration, start_cents=start, rest_cents=rest_cents, portion=portion)


def _duration_depth_scale(duration: float, *, reference_sec: float = 0.55) -> float:
    """Short notes get much less gamaka depth to avoid jitter."""
    if duration < 0.35:
        return 0.2
    if duration < _MIN_JARU_DURATION:
        return 0.35
    if duration < _MIN_KAMPITA_DURATION:
        return 0.55
    if duration < reference_sec:
        return max(0.65, duration / reference_sec)
    return min(1.0, 0.8 + duration / reference_sec * 0.2)


def _scale_curve_values(
    curve: list[tuple[float, float]],
    *,
    rest_cents: float,
    depth_scale: float,
) -> list[tuple[float, float]]:
    """Scale motion away from resting pitch; resting pitch is never scaled down."""
    if depth_scale == 1.0:
        return list(curve)
    scaled: list[tuple[float, float]] = []
    for t, cents in curve:
        scaled.append((t, rest_cents + (cents - rest_cents) * depth_scale))
    return scaled


def _dedupe_bend_curve(points: list[tuple[float, float]]) -> tuple[tuple[float, float], ...]:
    """One pitch-bend value per timestamp (later point wins)."""
    if not points:
        return ()
    ordered = sorted(points, key=lambda item: item[0])
    merged: list[tuple[float, float]] = []
    for t, cents in ordered:
        if merged and abs(merged[-1][0] - t) < 1e-5:
            merged[-1] = (t, cents)
        else:
            merged.append((t, cents))
    return tuple(merged)


def _compose_bend_curve(
    curves: list[list[tuple[float, float]]],
    *,
    duration: float,
    rest_cents: float,
    depth_scale: float,
) -> tuple[tuple[float, float], ...]:
    points: list[tuple[float, float]] = []
    for curve in curves:
        points.extend(_scale_curve_values(curve, rest_cents=rest_cents, depth_scale=depth_scale))
    if not points:
        if rest_cents:
            return ((0.0, rest_cents), (duration, rest_cents))
        return ()
    deduped = list(_dedupe_bend_curve(points))
    if deduped[0][0] > 0.0:
        deduped.insert(0, (0.0, deduped[0][1]))
    if deduped[-1][0] < duration:
        deduped.append((duration, deduped[-1][1]))
    return _dedupe_bend_curve(deduped)


def _append_kampita_after_jaru(
    jaru: list[tuple[float, float]],
    duration: float,
    *,
    rest_cents: float,
    depth_cents: float,
    cycles: float,
) -> list[tuple[float, float]]:
    """After a slide settles, add kampita on the remaining sustain."""
    if not jaru or duration <= 0 or duration < _MIN_KAMPITA_DURATION:
        return jaru
    settle_candidates = [t for t, c in jaru if abs(c - rest_cents) < 1.0 and t > 0]
    settle_t = min(settle_candidates) if settle_candidates else duration * 0.45
    remain = duration - settle_t
    if remain < 0.22 or depth_cents <= 0:
        return jaru
    kamp = _kampita_curve(remain, depth_cents=depth_cents, cycles=cycles, base_cents=rest_cents)
    return list(jaru) + [(settle_t + t, c) for t, c in kamp if t > 0]


def _curve_for_rule(
    rule: dict,
    note: TimedNote,
    prev: SwaraToken | None,
    curr: SwaraToken,
    nxt: SwaraToken | None,
    raga: dict,
    *,
    tonic_midi: int | None = None,
    allow_jaru: bool,
    allow_kampita: bool,
) -> list[tuple[float, float]]:
    gamaka_type = rule.get("type", "kampita")
    depth_cents = float(rule.get("depth_cents", 30))
    from_prev = bool(rule.get("from_prev", True))
    rest_cents = _shruti_bend(curr, raga)

    if gamaka_type == "kampita":
        if not allow_kampita:
            return []
        return _kampita_curve(
            note.duration,
            depth_cents=depth_cents,
            cycles=float(rule.get("cycles", 1)),
            base_cents=rest_cents,
        )

    if gamaka_type == "jaru_in":
        if not allow_jaru:
            return []
        portion = float(rule.get("portion", 0.45))
        if from_prev and prev is not None:
            start = _approach_bend_cents(
                prev,
                curr,
                raga,
                tonic_midi=tonic_midi,
                max_cents=float(rule.get("max_cents", _MAX_BEND_CENTS)),
            )
            jaru = _jaru_in_curve(
                note.duration,
                start_cents=start,
                rest_cents=rest_cents,
                portion=portion,
            )
            if rule.get("then_kampita") and allow_kampita:
                jaru = _append_kampita_after_jaru(
                    jaru,
                    note.duration,
                    rest_cents=rest_cents,
                    depth_cents=float(rule.get("kampita_depth", depth_cents * 0.6)),
                    cycles=float(rule.get("kampita_cycles", 1.0)),
                )
            return jaru
        from_above = True
        if prev is not None:
            from_above = swara_to_midi(prev, raga, tonic_midi=tonic_midi) > swara_to_midi(
                curr, raga, tonic_midi=tonic_midi
            )
        return _jaru_in_legacy(
            note.duration,
            depth_cents=min(depth_cents, _MAX_BEND_CENTS),
            portion=portion,
            from_above=from_above,
            rest_cents=rest_cents,
        )

    if gamaka_type == "jaru_out" and nxt is not None:
        if not allow_jaru:
            return []
        portion = float(rule.get("portion", 0.35))
        end = _departure_bend_cents(
            curr,
            nxt,
            raga,
            tonic_midi=tonic_midi,
            strength=float(rule.get("strength", 0.55)),
            max_cents=float(rule.get("max_cents", _MAX_BEND_CENTS)),
        )
        return _jaru_out_curve(
            note.duration,
            rest_cents=rest_cents,
            end_cents=end,
            portion=portion,
        )

    return []


def _connecting_jaru_in(
    note: TimedNote,
    prev: SwaraToken | None,
    curr: SwaraToken,
    raga: dict,
    *,
    tonic_midi: int | None = None,
) -> list[tuple[float, float]]:
    """Approach current swara from previous pitch when no explicit rule matched."""
    if prev is None or note.duration < _MIN_JARU_DURATION:
        return []
    prev_pitch = swara_to_midi(prev, raga, tonic_midi=tonic_midi)
    curr_pitch = swara_to_midi(curr, raga, tonic_midi=tonic_midi)
    interval = abs(prev_pitch - curr_pitch)
    if interval == 0 or interval > 7:
        return []
    rest_cents = _shruti_bend(curr, raga)
    start = _approach_bend_cents(prev, curr, raga, tonic_midi=tonic_midi)
    portion = 0.45 if interval <= 2 else 0.38 if interval <= 4 else 0.32
    return _jaru_in_curve(
        note.duration,
        start_cents=start,
        rest_cents=rest_cents,
        portion=portion,
    )


def _jeeva_kampita(
    note: TimedNote,
    curr: SwaraToken,
    raga: dict,
) -> list[tuple[float, float]]:
    """Extra oscillation on jeeva swaras (sustained notes only)."""
    if note.duration < _MIN_KAMPITA_DURATION:
        return []
    jeeva = set(raga.get("jeeva_swaras", list(_JEEVA_DEFAULT)))
    if curr.name not in jeeva:
        return []
    rest_cents = _shruti_bend(curr, raga)
    if note.duration < 0.85:
        depth, cycles = 24.0, 1.0
    else:
        depth, cycles = 42.0, min(2.2, 0.9 + note.duration * 0.6)
    return _kampita_curve(
        note.duration,
        depth_cents=depth,
        cycles=cycles,
        base_cents=rest_cents,
    )


def _sustain_kampita(duration: float, *, rest_cents: float) -> list[tuple[float, float]]:
    if duration < _MIN_SUSTAIN_KAMPITA:
        return []
    cycles = min(2.4, 0.8 + duration * 0.6)
    return _kampita_curve(duration, depth_cents=32.0, cycles=cycles, base_cents=rest_cents)


def apply_gamakas(
    notes: list[TimedNote],
    events: list[ParsedEvent],
    raga: dict,
    *,
    tonic_midi: int | None = None,
    depth_scale: float = 1.0,
    connecting_jarus: bool = False,
) -> list[TimedNote]:
    """Attach pitch-bend curves to timed notes using raga gamaka_rules."""
    rules: list[dict] = raga.get("gamaka_rules", [])
    if not notes:
        return notes
    if not rules and not connecting_jarus:
        return notes

    swaras = _note_swara_sequence(events)
    if len(swaras) != len(notes):
        return notes

    enriched: list[TimedNote] = []
    for i, note in enumerate(notes):
        prev = swaras[i - 1] if i > 0 else None
        curr = swaras[i]
        nxt = swaras[i + 1] if i + 1 < len(swaras) else None
        rest_cents = note.pitch_offset_cents or _shruti_bend(curr, raga)

        allow_jaru = note.duration >= _MIN_JARU_DURATION
        allow_kampita = note.duration >= _MIN_KAMPITA_DURATION

        curves: list[list[tuple[float, float]]] = []
        matched_type: str | None = None
        for rule in rules:
            if _rule_matches(rule, prev, curr, nxt):
                curve = _curve_for_rule(
                    rule,
                    note,
                    prev,
                    curr,
                    nxt,
                    raga,
                    tonic_midi=tonic_midi,
                    allow_jaru=allow_jaru,
                    allow_kampita=allow_kampita,
                )
                if curve:
                    curves.append(curve)
                matched_type = str(rule.get("type", "kampita"))
                break

        has_approach = matched_type == "jaru_in" or any(
            curve and abs(curve[0][1] - rest_cents) > 20 for curve in curves
        )
        if connecting_jarus and allow_jaru and prev is not None and not has_approach:
            approach = _connecting_jaru_in(note, prev, curr, raga, tonic_midi=tonic_midi)
            if approach:
                curves.append(approach)
                matched_type = "jaru_in"

        if (
            allow_kampita
            and matched_type not in {"jaru_in", "jaru_out", "kampita"}
        ):
            jeeva = _jeeva_kampita(note, curr, raga)
            if jeeva:
                curves.append(jeeva)

        if not curves and note.duration >= _MIN_SUSTAIN_KAMPITA:
            sustain = _sustain_kampita(note.duration, rest_cents=rest_cents)
            if sustain:
                curves.append(sustain)

        note_depth = depth_scale * _duration_depth_scale(note.duration)

        if curves or rest_cents:
            merged = _compose_bend_curve(
                curves,
                duration=note.duration,
                rest_cents=rest_cents,
                depth_scale=note_depth,
            )
            merged = tuple((t, _clamp_cents(c)) for t, c in merged)
            enriched.append(
                TimedNote(
                    pitch=note.pitch,
                    start=note.start,
                    duration=note.duration,
                    velocity=note.velocity,
                    pitch_offset_cents=0.0,
                    pitch_bends=merged,
                )
            )
        else:
            enriched.append(
                TimedNote(
                    pitch=note.pitch,
                    start=note.start,
                    duration=note.duration,
                    velocity=note.velocity,
                    pitch_offset_cents=0.0,
                    pitch_bends=(),
                )
            )

    return enriched
