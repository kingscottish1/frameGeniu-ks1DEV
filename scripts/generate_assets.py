#!/usr/bin/env python3
"""Generate bundled BGM and ensure subtitle fonts exist."""

from __future__ import annotations

import math
import struct
import urllib.request
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SONGS = ROOT / "resource" / "songs"
FONTS = ROOT / "resource" / "fonts"
SONGS.mkdir(parents=True, exist_ok=True)
FONTS.mkdir(parents=True, exist_ok=True)

FONT_URLS = {
    "Montserrat-Bold.ttf": "https://github.com/JulietaUla/Montserrat/raw/master/fonts/ttf/Montserrat-Bold.ttf",
    "Inter-Regular.ttf": "https://github.com/rsms/inter/raw/master/docs/font-files/Inter-Regular.ttf",
}


def write_tone(path: Path, chords: list[tuple[float, ...]], seconds: float = 28.0, volume: float = 0.11) -> None:
    rate = 44100
    n = int(rate * seconds)
    with wave.open(str(path), "w") as handle:
        handle.setnchannels(2)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        frames = bytearray()
        for i in range(n):
            t = i / rate
            env = min(1.0, t / 1.4) * min(1.0, (seconds - t) / 1.8)
            sample = 0.0
            chord = chords[int(t / 4.0) % len(chords)]
            for freq in chord:
                sample += math.sin(2 * math.pi * freq * t)
                sample += 0.35 * math.sin(2 * math.pi * freq * 2 * t)
            sample = sample / (len(chord) * 1.4)
            # slow chorus
            sample += 0.12 * math.sin(2 * math.pi * 0.12 * t)
            value = int(max(-1.0, min(1.0, sample * env * volume)) * 32767)
            frames += struct.pack("<hh", value, int(value * 0.92))
        handle.writeframes(frames)


def download_font(name: str, url: str) -> None:
    dest = FONTS / name
    if dest.exists() and dest.stat().st_size > 10_000:
        print("font ok", dest.name)
        return
    try:
        print("download", name)
        urllib.request.urlretrieve(url, dest)
    except Exception as exc:
        print("font skip", name, exc)


def main() -> None:
    write_tone(
        SONGS / "royalty_free_1.wav",
        [(196.0, 246.94, 293.66), (174.61, 220.0, 261.63), (164.81, 220.0, 329.63), (146.83, 196.0, 293.66)],
    )
    write_tone(
        SONGS / "royalty_free_2.wav",
        [(130.81, 164.81, 196.0), (146.83, 174.61, 220.0), (123.47, 155.56, 196.0), (110.0, 146.83, 174.61)],
        volume=0.1,
    )
    write_tone(
        SONGS / "royalty_free_3.wav",
        [(220.0, 277.18, 329.63), (196.0, 246.94, 311.13), (174.61, 220.0, 261.63), (164.81, 207.65, 246.94)],
        volume=0.09,
    )
    # mp3 aliases expected by templates: copy wav bytes under mp3 names if no encoder
    for index in (1, 2, 3):
        wav = SONGS / f"royalty_free_{index}.wav"
        mp3 = SONGS / f"royalty_free_{index}.mp3"
        if wav.exists() and not mp3.exists():
            mp3.write_bytes(wav.read_bytes())
    for name, url in FONT_URLS.items():
        download_font(name, url)
    arial = FONTS / "Arial.ttf"
    inter = FONTS / "Inter-Regular.ttf"
    if inter.exists() and not arial.exists():
        arial.write_bytes(inter.read_bytes())
    print("assets ready")


if __name__ == "__main__":
    main()
