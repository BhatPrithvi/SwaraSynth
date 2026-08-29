# SwaraSynth

> **Status: archived experiment (private).** Not maintained; not recommended for Carnatic study.
>
> SwaraSynth turns Shivkumar-style swara notation into **dry practice audio** — syllable rhythm, tala clicks, and a piano sketch of pitch and speed. It is a **notation and laya checker**, not a guru, not a raga synthesizer, and not a substitute for lesson recordings or singing with your teacher. **No teacher would recommend this for learning gayaki, shruti, or raga ethos.** Use a real reference recording and your teacher's guidance for that. Expressive mode (violin + gamaka) remains experimental and does not reproduce Charukeshi or kriti phrasing.

Carnatic swara notation → practice audio. Renders kriti sections with **Misra Chapu timing**, **tanpura drone**, **tala clicks**, and **looping** for practice.

## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

On Raspberry Pi / Debian, install a GM soundfont for practice audio:

```bash
sudo apt install fluid-soundfont-gm
```

## Practice (tutor mode)

Renders **piano** (clear pitches) with **syllable rhythm**, **tanpura**, and **tala clicks**. No gamaka by default — use a lesson recording for ornament.

```bash
swarasynth list-pieces
swarasynth practice krupaya_palaya --section pallavi --loop 4 --tonic E -o pallavi.wav
swarasynth practice krupaya_palaya --section karuna --loop 2 -o karuna.wav --midi
```

Optional expressive mode (experimental — not recommended):

```bash
swarasynth practice krupaya_palaya --section pallavi --expressive -o expressive.wav
```

`--expressive` enables violin + gamaka. It does not sound like a vocal or violin lesson and is not suitable for learning ornament or intonation.

Sections: `pallavi`, `karuna`, `kalusha`, `paahi`, `anupallavi`, `charanam`

Options: `--loop`, `--tonic`, `--program 0|40`, `--expressive`, `--no-tanpura`, `--no-clicks`, `--gamaka` / `--no-gamaka`, `--midi`

## MIDI export (legacy)

```bash
swarasynth render examples/krupaya_palaya/pallavi.txt -o out.mid --tonic E --no-gamaka
```

## Notation

- Swaras: `S`, `R1`–`R3`, `G1`–`G3`, `M1`–`M2`, `P`, `D1`–`D3`, `N1`–`N3`
- Octave: `'` upper, `.` lower (`S'`, `.S`)
- Shivkumar speed: **lowercase = double speed** (`P M m g g r S`); uppercase = normal
- `,` lengthens the **previous** swara (place after sustained syllables: `S' , R2` not `R2 ,`)
- `;` double hold

## Layout

```
src/swarasynth/   parser, tuning, tala, audio, practice, CLI
pieces/           kriti manifests (sections, tala, tonic)
examples/         per-section notation files
ragas/            raga profiles
```

## Example

*Krupaya Palaya Sauri* (Swati Tirunal, Charukeshi, Misra Chapu) from [shivkumar.org](https://www.shivkumar.org/music/krupayapalaya.htm) — `pieces/krupaya_palaya.json` + `examples/krupaya_palaya/`

MIT license.
