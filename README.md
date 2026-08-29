# SwaraSynth

Carnatic swara notation → MIDI.

Paste notation like `P , D1 P M1 G3 , M1 R2 S ,`, pick a raga profile, get a `.mid` file. Gamakas are not applied yet — notes are plain swaras with comma holds.

## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Usage

```bash
swarasynth list-ragas
swarasynth show examples/krupaya_palaya_opening.txt
swarasynth render examples/krupaya_palaya_opening.txt -o out.mid --raga charukeshi
```

Options: `--tempo`, `--beat`, `--hold`.

## Notation

- Swaras: `S`, `R1`–`R3`, `G1`–`G3`, `M1`–`M2`, `P`, `D1`–`D3`, `N1`–`N3`
- Octave: `'` upper, `.` lower (`S'`, `.S`)
- `,` lengthens the previous note

## Example

Opening of *Krupaya Palaya Sauri* (Swati Tirunal), raga Charukeshi — see `examples/krupaya_palaya_opening.txt`.

## Layout

```
src/swarasynth/   parser, tuning, MIDI writer, CLI
ragas/            raga JSON (scale + pitch map)
examples/
tests/
```

MIT license.
