# SwaraSynth

Carnatic swara notation → MIDI, with optional raga gamakas (pitch bend).

Paste notation like `P , D1 P M1 G3 , M1 R2 S ,`, pick a raga profile, get a `.mid` file. Gamakas are applied from JSON rules in each raga profile (kampita oscillation, jaru slides). Use `--no-gamaka` for plain swaras.

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
swarasynth render examples/krupaya_palaya_opening.txt -o plain.mid --no-gamaka
```

Options: `--tempo`, `--beat`, `--hold`, `--no-gamaka`.

## Notation

- Swaras: `S`, `R1`–`R3`, `G1`–`G3`, `M1`–`M2`, `P`, `D1`–`D3`, `N1`–`N3`
- Octave: `'` upper, `.` lower (`S'`, `.S`)
- `,` lengthens the previous note

## Gamaka rules

Raga JSON files include a `gamaka_rules` list. Each rule matches a swara (optionally `when_prev` / `when_next`) and applies:

| type | effect |
|------|--------|
| `kampita` | oscillation around the written pitch (`depth_cents`, `cycles`) |
| `jaru_in` | slide into the note from the previous swara (`depth_cents`, `portion`) |
| `jaru_out` | slide out toward the next swara (`depth_cents`, `portion`) |

## Example

Opening of *Krupaya Palaya Sauri* (Swati Tirunal), raga Charukeshi — see `examples/krupaya_palaya_opening.txt`.

## Layout

```
src/swarasynth/   parser, tuning, MIDI writer, CLI
ragas/            raga JSON (scale, pitch map, gamaka rules)
examples/
tests/
```

MIT license.
