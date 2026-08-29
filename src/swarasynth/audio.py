"""Synthesize practice audio: melody, tanpura drone, tala clicks."""

from __future__ import annotations

import math
import struct
import wave
from pathlib import Path

import numpy as np

from swarasynth.midi_writer import notes_to_pretty_midi
from swarasynth.models import TimedNote

SAMPLE_RATE = 44100

SOUNDFONT_CANDIDATES = (
    "/usr/share/sounds/sf2/FluidR3_GM.sf2",
    "/usr/share/sounds/sf2/default-GM.sf2",
    "/usr/share/sounds/sf2/TimGM6mb.sf2",
)

PRACTICE_LEGATO_OVERLAP = 0.12
PRACTICE_VIOLIN_VELOCITY = 78


def find_soundfont() -> Path:
    """Return the first available GM soundfont path."""
    for candidate in SOUNDFONT_CANDIDATES:
        path = Path(candidate)
        if path.is_file():
            return path
    try:
        import pretty_midi

        bundled = Path(pretty_midi.__file__).with_name("TimGM6mb.sf2")
        if bundled.is_file():
            return bundled
    except ImportError:
        pass
    raise FileNotFoundError(
        "No GM soundfont found. Install one, e.g. "
        "`sudo apt install fluid-soundfont-gm` on Debian/Raspberry Pi OS."
    )


def midi_to_hz(midi: int) -> float:
    return 440.0 * (2.0 ** ((midi - 69) / 12.0))


def _sine_sample(phase: float, amplitude: float) -> float:
    return amplitude * math.sin(phase)


def render_tanpura(
    duration_sec: float,
    sa_hz: float,
    *,
    sample_rate: int = SAMPLE_RATE,
    amplitude: float = 0.08,
) -> list[float]:
    """Simple tanpura drone: Sa, lower Sa, Pa with slow amplitude swell."""
    pa_hz = sa_hz * (3.0 / 2.0)
    sa_low = sa_hz / 2.0
    n = int(duration_sec * sample_rate)
    t = np.arange(n, dtype=np.float64) / sample_rate
    swell = 0.85 + 0.15 * np.sin(2 * np.pi * 0.25 * t)
    sample = (
        0.5 * np.sin(2 * np.pi * sa_hz * t)
        + 0.3 * np.sin(2 * np.pi * sa_low * t)
        + 0.2 * np.sin(2 * np.pi * pa_hz * t)
    ) * amplitude * swell
    return sample.tolist()


def render_instrument_melody(
    notes: list[TimedNote],
    *,
    sample_rate: int = SAMPLE_RATE,
    program: int = 0,
    legato_overlap: float = PRACTICE_LEGATO_OVERLAP,
    legato_overlaps: list[float] | None = None,
    soundfont: Path | str | None = None,
    melody_gain: float = 0.85,
) -> tuple[list[float], float]:
    """Synthesize melody with FluidSynth (piano tutor default, or violin)."""
    if not notes:
        return [], 0.0

    practice_notes = [
        TimedNote(
            pitch=n.pitch,
            start=n.start,
            duration=n.duration,
            velocity=n.velocity if n.velocity != 90 else PRACTICE_VIOLIN_VELOCITY,
            pitch_bends=n.pitch_bends,
        )
        for n in notes
    ]
    pm = notes_to_pretty_midi(
        practice_notes,
        program=program,
        legato_overlap=legato_overlap,
        legato_overlaps=legato_overlaps,
    )
    sf_path = Path(soundfont) if soundfont is not None else find_soundfont()
    audio = pm.fluidsynth(fs=sample_rate, synthesizer=str(sf_path))
    end = max(n.start + n.duration for n in notes)
    return (audio * melody_gain).tolist(), end


def render_violin_melody(
    notes: list[TimedNote],
    *,
    sample_rate: int = SAMPLE_RATE,
    program: int = 40,
    legato_overlap: float = PRACTICE_LEGATO_OVERLAP,
    legato_overlaps: list[float] | None = None,
    soundfont: Path | str | None = None,
    melody_gain: float = 0.85,
) -> tuple[list[float], float]:
    """Backward-compatible alias for violin program 40."""
    return render_instrument_melody(
        notes,
        sample_rate=sample_rate,
        program=program,
        legato_overlap=legato_overlap,
        legato_overlaps=legato_overlaps,
        soundfont=soundfont,
        melody_gain=melody_gain,
    )


def render_melody(
    notes: list[TimedNote],
    *,
    sample_rate: int = SAMPLE_RATE,
    amplitude: float = 0.35,
) -> tuple[list[float], float]:
    """Sine-wave melody with short attack/release (practice reference)."""
    if not notes:
        return [], 0.0
    end = max(n.start + n.duration for n in notes)
    n = int((end + 0.1) * sample_rate)
    buf = [0.0] * n
    for note in notes:
        hz = midi_to_hz(note.pitch)
        start_i = int(note.start * sample_rate)
        end_i = int((note.start + note.duration) * sample_rate)
        attack = max(1, int(0.015 * sample_rate))
        release = max(1, int(0.04 * sample_rate))
        phase = 0.0
        phase_inc = 2 * math.pi * hz / sample_rate
        for i in range(start_i, min(end_i, n)):
            rel = i - start_i
            note_len = end_i - start_i
            env = 1.0
            if rel < attack:
                env = rel / attack
            elif note_len - rel < release:
                env = max(0.0, (note_len - rel) / release)
            buf[i] += _sine_sample(phase, amplitude * env)
            phase += phase_inc
    return buf, end


def render_clicks(
    times: list[float],
    duration_sec: float,
    *,
    sample_rate: int = SAMPLE_RATE,
    amplitude: float = 0.045,
) -> list[float]:
    n = int((duration_sec + 0.1) * sample_rate)
    buf = [0.0] * n
    click_len = int(0.018 * sample_rate)
    for t in times:
        start = int(t * sample_rate)
        for i in range(click_len):
            idx = start + i
            if idx >= n:
                break
            env = 1.0 - (i / click_len)
            buf[idx] += amplitude * env * math.sin(2 * math.pi * 800 * i / sample_rate)
    return buf


def mix_buffers(*buffers: list[float]) -> list[float]:
    length = max(len(b) for b in buffers) if buffers else 0
    out = [0.0] * length
    for buf in buffers:
        for i, v in enumerate(buf):
            out[i] += v
    return out


def normalize(buf: list[float], peak: float = 0.9) -> list[float]:
    max_abs = max((abs(v) for v in buf), default=0.0)
    if max_abs <= 0:
        return buf
    scale = peak / max_abs
    return [v * scale for v in buf]


def write_wav(path: Path, buf: list[float], *, sample_rate: int = SAMPLE_RATE) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    clipped = normalize(buf)
    with wave.open(str(path), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        frames = bytearray()
        for v in clipped:
            sample = int(max(-1.0, min(1.0, v)) * 32767)
            frames.extend(struct.pack("<h", sample))
        wf.writeframes(frames)
    return path


def loop_notes(notes: list[TimedNote], loops: int, *, gap_sec: float = 0.8) -> list[TimedNote]:
    if loops <= 1 or not notes:
        return list(notes)
    end = max(n.start + n.duration for n in notes)
    block = end + gap_sec
    out: list[TimedNote] = []
    for loop in range(loops):
        offset = loop * block
        for n in notes:
            out.append(
                TimedNote(
                    pitch=n.pitch,
                    start=n.start + offset,
                    duration=n.duration,
                    velocity=n.velocity,
                    pitch_offset_cents=n.pitch_offset_cents,
                    pitch_bends=tuple((t + offset, c) for t, c in n.pitch_bends),
                )
            )
    return out
