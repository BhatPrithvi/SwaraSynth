"""Carnatic tala timing: aksharam-based note scheduling."""

from __future__ import annotations

from pathlib import Path

from swarasynth.gamaka import apply_gamakas
from swarasynth.models import EventKind, ParsedEvent, TimedNote
from swarasynth.syllable_rhythm import (
    align_groups,
    group_durations,
    load_section_rhythm,
    note_speeds_from_events,
)
from swarasynth.tuning import load_raga, swara_shruti_cents, swara_to_midi

TALA_PROFILES: dict[str, dict[str, float]] = {
    "misra_chapu": {
        "note_aksharams": 1.0,
        "hold_aksharams": 2.0,
        "default_apm": 100.0,
    },
    "adi": {
        "note_aksharams": 1.0,
        "hold_aksharams": 2.0,
        "default_apm": 120.0,
    },
}


def aksharams_to_seconds(aksharams: float, aksharams_per_minute: float) -> float:
    if aksharams_per_minute <= 0:
        raise ValueError("aksharams_per_minute must be positive")
    return aksharams * (60.0 / aksharams_per_minute)


def _with_shruti_offset(
    note: TimedNote,
    swara,
    raga: dict,
) -> TimedNote:
    cents = swara_shruti_cents(swara, raga)
    if cents == 0.0:
        return note
    return TimedNote(
        pitch=note.pitch,
        start=note.start,
        duration=note.duration,
        velocity=note.velocity,
        pitch_offset_cents=cents,
        pitch_bends=note.pitch_bends,
    )


def _note_durations_from_syllable_rhythm(
    events: list[ParsedEvent],
    *,
    piece_id: str,
    section: str,
    sec_per_aksharam: float,
    pieces_dir: Path | None,
) -> list[float] | None:
    groups = load_section_rhythm(piece_id, section, pieces_dir)
    if groups is None:
        return None
    note_count = sum(1 for ev in events if ev.kind == EventKind.NOTE)
    groups = align_groups(groups, note_count)
    speeds = note_speeds_from_events(events)
    return group_durations(groups, sec_per_aksharam=sec_per_aksharam, speeds=speeds)


def events_to_timed_notes_tala(
    events: list[ParsedEvent],
    raga_name: str,
    *,
    tala: str = "misra_chapu",
    aksharams_per_minute: float | None = None,
    ragas_dir: Path | None = None,
    apply_gamaka_rules: bool = False,
    tonic_midi: int | None = None,
    note_aksharams: float | None = None,
    hold_aksharams: float | None = None,
    opening_hold_aksharams: float | None = None,
    comma_hold_aksharams: float | None = None,
    gamaka_depth: float = 1.0,
    connecting_jarus: bool = False,
    apply_shruti: bool = False,
    syllable_rhythm: bool = False,
    piece_id: str | None = None,
    section: str | None = None,
    pieces_dir: Path | None = None,
) -> list[TimedNote]:
    """Schedule parsed events using aksharam counts (Carnatic tala feel)."""
    profile = TALA_PROFILES.get(tala)
    if profile is None:
        raise ValueError(f"Unknown tala: {tala!r}")

    apm = aksharams_per_minute if aksharams_per_minute is not None else profile["default_apm"]
    note_aks = note_aksharams if note_aksharams is not None else profile["note_aksharams"]
    hold_aks = hold_aksharams if hold_aksharams is not None else profile["hold_aksharams"]

    raga = load_raga(raga_name, ragas_dir)
    sec_per_aksharam = 60.0 / apm

    syllable_durs: list[float] | None = None
    if syllable_rhythm and piece_id and section:
        syllable_durs = _note_durations_from_syllable_rhythm(
            events,
            piece_id=piece_id,
            section=section,
            sec_per_aksharam=sec_per_aksharam,
            pieces_dir=pieces_dir,
        )

    notes: list[TimedNote] = []
    t = 0.0
    last_note_idx: int | None = None
    note_idx = 0
    hold_idx = 0

    for ev in events:
        if ev.kind == EventKind.HOLD:
            hold_aks_use = hold_aks
            if syllable_durs is not None and comma_hold_aksharams is not None:
                hold_aks_use = comma_hold_aksharams
            elif (
                opening_hold_aksharams is not None
                and section == "pallavi"
                and hold_idx == 0
            ):
                hold_aks_use = opening_hold_aksharams
            hold_idx += 1
            extra = hold_aks_use * sec_per_aksharam
            if last_note_idx is not None:
                prev = notes[last_note_idx]
                notes[last_note_idx] = TimedNote(
                    pitch=prev.pitch,
                    start=prev.start,
                    duration=prev.duration + extra,
                    velocity=prev.velocity,
                    pitch_offset_cents=prev.pitch_offset_cents,
                    pitch_bends=prev.pitch_bends,
                )
                t += extra
            else:
                t += extra
            continue

        assert ev.swara is not None
        pitch = swara_to_midi(ev.swara, raga, tonic_midi=tonic_midi)
        if syllable_durs is not None:
            dur = syllable_durs[note_idx]
        else:
            speed = ev.swara.speed if ev.swara.speed > 0 else 1.0
            dur = note_aks * sec_per_aksharam / speed
        note = TimedNote(pitch=pitch, start=t, duration=dur)
        if apply_shruti:
            note = _with_shruti_offset(note, ev.swara, raga)
        notes.append(note)
        last_note_idx = len(notes) - 1
        note_idx += 1
        t += dur

    if apply_gamaka_rules:
        notes = apply_gamakas(
            notes,
            events,
            raga,
            tonic_midi=tonic_midi,
            depth_scale=gamaka_depth,
            connecting_jarus=connecting_jarus,
        )
    elif apply_shruti:
        notes = [
            TimedNote(
                pitch=n.pitch,
                start=n.start,
                duration=n.duration,
                velocity=n.velocity,
                pitch_offset_cents=n.pitch_offset_cents,
                pitch_bends=((0.0, n.pitch_offset_cents),) if n.pitch_offset_cents else (),
            )
            for n in notes
        ]

    return notes


def misra_chapu_clicks(
    duration_sec: float,
    *,
    aksharams_per_minute: float = 100.0,
    gap_sec: float = 0.0,
) -> list[float]:
    """Return click times for Misra Chapu (7 aksharams per avartan)."""
    sec_per_aksharam = 60.0 / aksharams_per_minute
    cycle = 7 * sec_per_aksharam
    clicks: list[float] = []
    t = gap_sec
    while t < duration_sec:
        for beat in range(7):
            click_t = t + beat * sec_per_aksharam
            if click_t < duration_sec:
                clicks.append(click_t)
        t += cycle
    return clicks
