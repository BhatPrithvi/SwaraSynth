"""Command-line interface for SwaraSynth."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from swarasynth.parser import parse_notation
from swarasynth.tuning import RAGAS_DIR, load_raga
from swarasynth.midi_writer import render_notation_to_midi


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
    out = render_notation_to_midi(
        notation,
        Path(args.output),
        raga_name=args.raga,
        tempo_bpm=args.tempo,
        beats_per_note=args.beat,
        hold_beats=args.hold,
    )
    print(f"Wrote {out}")
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
    render_p.add_argument("--tempo", type=float, default=60.0, help="Tempo BPM")
    render_p.add_argument("--beat", type=float, default=0.5, help="Beats per swara")
    render_p.add_argument("--hold", type=float, default=0.5, help="Beats added per comma hold")
    render_p.set_defaults(func=cmd_render)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
