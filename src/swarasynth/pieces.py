"""Load practice piece manifests."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

PIECES_DIR = Path(__file__).resolve().parents[2] / "pieces"


@dataclass(frozen=True)
class PieceSection:
    name: str
    notation_path: Path
    description: str = ""


@dataclass(frozen=True)
class PracticeSettings:
    """Defaults favor tutor clarity (piano, no gamaka). Use expressive flags for violin."""

    gamaka: bool = False
    gamaka_depth: float = 0.75
    connecting_jarus: bool = False
    syllable_rhythm: bool = True
    syllable_articulation: bool = True
    group_gap_ms: float = 40.0
    apply_shruti: bool = False
    instrument_program: int = 0  # GM 0=piano (tutor), 40=violin
    aksharams_per_minute: float | None = None
    hold_aksharams: float | None = None
    opening_hold_aksharams: float | None = None
    comma_hold_aksharams: float | None = None


@dataclass(frozen=True)
class Piece:
    id: str
    title: str
    raga: str
    tala: str
    tonic_default: str
    aksharams_per_minute: float
    sections: tuple[PieceSection, ...]
    source: str = ""
    practice: PracticeSettings = field(default_factory=PracticeSettings)

    def section(self, name: str) -> PieceSection:
        for sec in self.sections:
            if sec.name == name:
                return sec
        names = ", ".join(s.name for s in self.sections)
        raise KeyError(f"Unknown section {name!r}. Available: {names}")

    def load_section_notation(self, name: str) -> str:
        sec = self.section(name)
        return sec.notation_path.read_text(encoding="utf-8")


def list_pieces(pieces_dir: Path | None = None) -> list[str]:
    root = pieces_dir or PIECES_DIR
    return sorted(p.stem for p in root.glob("*.json"))


def load_piece(piece_id: str, pieces_dir: Path | None = None) -> Piece:
    root = pieces_dir or PIECES_DIR
    path = root / f"{piece_id.lower()}.json"
    if not path.exists():
        raise FileNotFoundError(f"Piece not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    piece_root = path.parent
    project_root = piece_root.parent

    sections: list[PieceSection] = []
    for sec in data.get("sections", []):
        notation = Path(sec["notation"])
        if not notation.is_absolute():
            for base in (project_root, piece_root):
                candidate = base / notation
                if candidate.exists():
                    notation = candidate
                    break
        sections.append(
            PieceSection(
                name=sec["name"],
                notation_path=notation,
                description=sec.get("description", ""),
            )
        )

    return Piece(
        id=data["id"],
        title=data.get("title", data["id"]),
        raga=data.get("raga", "charukeshi"),
        tala=data.get("tala", "misra_chapu"),
        tonic_default=data.get("tonic_default", "C"),
        aksharams_per_minute=float(data.get("aksharams_per_minute", 100)),
        sections=tuple(sections),
        source=data.get("source", ""),
        practice=_load_practice_settings(data.get("practice", {})),
    )


def _load_practice_settings(raw: dict) -> PracticeSettings:
    return PracticeSettings(
        gamaka=bool(raw.get("gamaka", False)),
        gamaka_depth=float(raw.get("gamaka_depth", 0.75)),
        connecting_jarus=bool(raw.get("connecting_jarus", False)),
        syllable_rhythm=bool(raw.get("syllable_rhythm", True)),
        syllable_articulation=bool(raw.get("syllable_articulation", True)),
        group_gap_ms=float(raw.get("group_gap_ms", 40.0)),
        apply_shruti=bool(raw.get("apply_shruti", False)),
        instrument_program=int(raw.get("instrument_program", 0)),
        aksharams_per_minute=(
            float(raw["aksharams_per_minute"]) if "aksharams_per_minute" in raw else None
        ),
        hold_aksharams=float(raw["hold_aksharams"]) if "hold_aksharams" in raw else None,
        opening_hold_aksharams=(
            float(raw["opening_hold_aksharams"]) if "opening_hold_aksharams" in raw else None
        ),
        comma_hold_aksharams=(
            float(raw["comma_hold_aksharams"]) if "comma_hold_aksharams" in raw else None
        ),
    )
