"""Syllable-group rhythm: allocate aksharams per lyric group, not per swara."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

PIECES_DIR = Path(__file__).resolve().parents[2] / "pieces"


@dataclass(frozen=True)
class SyllableGroup:
    """A lyric syllable group spanning `note_count` consecutive swaras."""

    aksharams: float
    note_count: int


def _parse_groups(raw: list[list[float | int]]) -> tuple[SyllableGroup, ...]:
    groups: list[SyllableGroup] = []
    for item in raw:
        if len(item) != 2:
            raise ValueError(f"Each group must be [aksharams, note_count], got {item!r}")
        groups.append(SyllableGroup(aksharams=float(item[0]), note_count=int(item[1])))
    return tuple(groups)


def load_section_rhythm(piece_id: str, section: str, pieces_dir: Path | None = None) -> tuple[SyllableGroup, ...] | None:
    """Load flat syllable-group list for a section, or None if not defined."""
    root = pieces_dir or PIECES_DIR
    path = root / f"{piece_id.lower()}_rhythm.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    section_data = data.get(section)
    if section_data is None:
        return None
    if "groups" in section_data:
        return _parse_groups(section_data["groups"])
    if "lines" in section_data:
        flat: list[SyllableGroup] = []
        for line in section_data["lines"]:
            flat.extend(_parse_groups(line))
        return tuple(flat)
    return None


def group_durations(
    groups: tuple[SyllableGroup, ...],
    *,
    sec_per_aksharam: float,
    speeds: list[float] | None = None,
) -> list[float]:
    """Expand groups into per-note durations (seconds).

    When ``speeds`` is given, time within each group is split by inverse speed
    (Shivkumar lowercase = speed 2.0 = half duration).
    """
    durations: list[float] = []
    idx = 0
    for group in groups:
        if group.note_count <= 0:
            raise ValueError(f"note_count must be positive: {group}")
        group_sec = group.aksharams * sec_per_aksharam
        if speeds is not None:
            group_speeds = speeds[idx : idx + group.note_count]
            weights = [1.0 / speed for speed in group_speeds]
            total_weight = sum(weights)
            for weight in weights:
                durations.append(group_sec * (weight / total_weight))
        else:
            per_note = group_sec / group.note_count
            durations.extend([per_note] * group.note_count)
        idx += group.note_count
    return durations


def note_speeds_from_events(events) -> list[float]:
    from swarasynth.models import EventKind

    return [ev.swara.speed for ev in events if ev.kind == EventKind.NOTE and ev.swara is not None]


def count_notes(events) -> int:
    from swarasynth.models import EventKind

    return sum(1 for ev in events if ev.kind == EventKind.NOTE)


def validate_rhythm(groups: tuple[SyllableGroup, ...], note_count: int, *, section: str) -> None:
    expected = sum(g.note_count for g in groups)
    if expected != note_count:
        raise ValueError(
            f"Rhythm profile for {section!r} covers {expected} notes but notation has {note_count}"
        )


def align_groups(
    groups: tuple[SyllableGroup, ...],
    note_count: int,
) -> tuple[SyllableGroup, ...]:
    """Pad or trim groups so they cover exactly `note_count` swaras."""
    items = list(groups)
    total = sum(g.note_count for g in items)
    if total == note_count:
        return tuple(items)
    if total < note_count:
        items.append(SyllableGroup(aksharams=1.0, note_count=note_count - total))
        return tuple(items)
    while items and total > note_count:
        excess = total - note_count
        last = items[-1]
        if last.note_count > excess:
            items[-1] = SyllableGroup(last.aksharams, last.note_count - excess)
            total -= excess
        else:
            total -= last.note_count
            items.pop()
    return tuple(items)
