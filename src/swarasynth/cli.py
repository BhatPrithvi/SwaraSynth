"""Command-line interface for SwaraSynth."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from swarasynth.parser import parse_notation
from swarasynth.tuning import RAGAS_DIR, load_raga, parse_tonic
from swarasynth.midi_writer import render_notation_to_midi
from swarasynth.pieces import list_pieces, load_piece
from swarasynth.practice import run_practice


def cmd_list_ragas(_: argparse.Namespace) -> int:
    for path in sorted(RAGAS_DIR.glob("*.json")):
        raga = load_raga(path.stem)
        scale = " ".join(raga.get("scale", []))
        print(f"{path.stem}: {raga.get('description', '')} [{scale}]")
    return 0


def cmd_show_example(args: argparse.Namespace) -> int:
    path = Path(args.file)
    text = path.read_text(encoding="utf-8")
    print(text)
    events = parse_notation(text)
    print(f"\nParsed {len(events)} events:")
    for i, ev in enumerate(events):
        print(f"  {i:3d}  {ev.kind.value}  {ev.swara}")
    return 0


def cmd_render(args: argparse.Namespace) -> int:
    path = Path(args.input)
    notation = path.read_text(encoding="utf-8")
    tonic_midi = parse_tonic(args.tonic) if args.tonic is not None else None

    tempo_bpm = 60.0 if args.tempo is None else args.tempo
    beats_per_note = 0.5 if args.beat is None else args.beat
    hold_beats = 0.25 if args.hold is None else args.hold
    apply_gamaka = args.gamaka
    program = args.program

    if args.long:
        if args.tempo is None:
            tempo_bpm = 54.0
        if args.beat is None:
            beats_per_note = 1.0
        if args.hold is None:
            hold_beats = 0.35
        apply_gamaka = False
        program = 40

    if args.no_gamaka:
        apply_gamaka = False

    out = render_notation_to_midi(
        notation,
        Path(args.output),
        raga_name=args.raga,
        tempo_bpm=tempo_bpm,
        beats_per_note=beats_per_note,
        hold_beats=hold_beats,
        apply_gamaka_rules=apply_gamaka,
        tonic_midi=tonic_midi,
        program=program,
    )
    print(f"Wrote {out}")
    return 0


def cmd_list_pieces(_: argparse.Namespace) -> int:
    for pid in list_pieces():
        piece = load_piece(pid)
        secs = ", ".join(s.name for s in piece.sections)
        print(f"{pid}: {piece.title} [{piece.raga}, {piece.tala}] — {secs}")
    return 0


def cmd_practice(args: argparse.Namespace) -> int:
    apply_gamaka = False if args.no_gamaka else (True if args.gamaka else None)
    program = args.program
    if args.expressive:
        apply_gamaka = True if apply_gamaka is None else apply_gamaka
        if program is None:
            program = 40
    out = run_practice(
        args.piece,
        Path(args.output),
        section=args.section,
        loops=args.loop,
        tonic=args.tonic,
        apply_gamaka=apply_gamaka,
        instrument_program=program,
        tala_clicks=not args.no_clicks,
        tanpura=not args.no_tanpura,
        also_midi=args.midi,
    )
    print(f"Wrote {out}")
    if args.midi:
        print(f"Wrote {out.with_suffix('.mid')}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="swarasynth", description="SwaraSynth — swara notation to MIDI")
    sub = p.add_subparsers(dest="command", required=True)

    list_p = sub.add_parser("list-ragas", help="List available raga profiles")
    list_p.set_defaults(func=cmd_list_ragas)

    show_p = sub.add_parser("show", help="Show notation file and parsed events")
    show_p.add_argument("file", help="Path to notation .txt")
    show_p.set_defaults(func=cmd_show_example)

    render_p = sub.add_parser("render", help="Render notation to MIDI")
    render_p.add_argument("input", help="Input notation file")
    render_p.add_argument("-o", "--output", default="out.mid", help="Output MIDI path")
    render_p.add_argument("--raga", default="charukeshi", help="Raga profile name")
    render_p.add_argument(
        "--tonic",
        metavar="NOTE",
        help="Sa pitch as a note name (C#, F#4, Eb3) or MIDI number (default: raga profile)",
    )
    render_p.add_argument("--tempo", type=float, default=None, help="Tempo BPM (default: 60)")
    render_p.add_argument("--beat", type=float, default=None, help="Beats per swara (default: 0.5)")
    render_p.add_argument(
        "--hold",
        type=float,
        default=None,
        help="Beats added per comma hold (default: 0.25)",
    )
    render_p.add_argument(
        "--program",
        type=int,
        default=40,
        metavar="N",
        help="GM instrument program (40=violin, 0=piano; default: 40)",
    )
    render_p.add_argument(
        "--long",
        action="store_true",
        help="Slow render: 54 BPM, beat 1.0, hold 0.35, violin, no gamaka",
    )
    render_p.add_argument(
        "--gamaka",
        action="store_true",
        help="Enable raga gamaka pitch-bend rules",
    )
    render_p.add_argument(
        "--no-gamaka",
        action="store_true",
        help="Disable gamaka rules (default)",
    )
    render_p.set_defaults(func=cmd_render)

    pieces_p = sub.add_parser("list-pieces", help="List practice piece manifests")
    pieces_p.set_defaults(func=cmd_list_pieces)

    practice_p = sub.add_parser("practice", help="Render practice WAV with tala, tanpura, loop")
    practice_p.add_argument("piece", help="Piece id (e.g. krupaya_palaya)")
    practice_p.add_argument("-o", "--output", default="practice.wav", help="Output WAV path")
    practice_p.add_argument(
        "--section",
        help="Section name, or 'all' for full kriti (default: first section)",
    )
    practice_p.add_argument("--loop", type=int, default=2, help="Loop count (default: 2)")
    practice_p.add_argument("--tonic", help="Sa pitch (default: piece tonic_default)")
    practice_p.add_argument(
        "--program",
        type=int,
        default=None,
        metavar="N",
        help="GM instrument (0=piano tutor default, 40=violin)",
    )
    practice_p.add_argument(
        "--expressive",
        action="store_true",
        help="Violin + gamaka (overrides tutor defaults)",
    )
    practice_p.add_argument("--gamaka", action="store_true", help="Enable gamaka rules")
    practice_p.add_argument("--no-gamaka", action="store_true", help="Disable gamaka (tutor default)")
    practice_p.add_argument("--no-clicks", action="store_true", help="Disable tala click track")
    practice_p.add_argument("--no-tanpura", action="store_true", help="Disable tanpura drone")
    practice_p.add_argument("--midi", action="store_true", help="Also write MIDI alongside WAV")
    practice_p.set_defaults(func=cmd_practice)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
