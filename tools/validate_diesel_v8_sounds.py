#!/usr/bin/env python3
"""Validate generated BMW M67D44 sound assets for packaging."""
from pathlib import Path
import wave
import sys

ROOT = Path("build/bmw_m67d44_sounds")
EXPECTED = {
    "bmw_m67d44_start.wav": (2.0, 5.0),
    "bmw_m67d44_stop.wav": (1.0, 4.0),
    "bmw_m67d44_idle.wav": (6.0, 10.0),
    "bmw_m67d44_low.wav": (6.0, 10.0),
    "bmw_m67d44_accel.wav": (5.0, 9.0),
    "bmw_m67d44_high.wav": (6.0, 10.0),
    "bmw_m67d44_turbo.wav": (3.0, 7.0),
    "bmw_m67d44_gear.wav": (0.3, 1.0),
}

errors = []
for name, (min_seconds, max_seconds) in EXPECTED.items():
    path = ROOT / name
    if not path.is_file():
        errors.append(f"MISSING: {path}")
        continue
    try:
        with wave.open(str(path), "rb") as wav:
            channels = wav.getnchannels()
            width = wav.getsampwidth()
            rate = wav.getframerate()
            frames = wav.getnframes()
            duration = frames / rate if rate else 0
            if channels != 1:
                errors.append(f"{name}: expected mono, got {channels} channels")
            if width != 2:
                errors.append(f"{name}: expected 16-bit PCM, got {width * 8}-bit")
            if rate != 44100:
                errors.append(f"{name}: expected 44100 Hz, got {rate} Hz")
            if not min_seconds <= duration <= max_seconds:
                errors.append(f"{name}: duration {duration:.2f}s outside {min_seconds}-{max_seconds}s")
            print(f"OK {name}: {rate} Hz, {channels} ch, {width * 8}-bit, {duration:.2f}s")
    except (wave.Error, OSError) as exc:
        errors.append(f"{name}: cannot read WAV ({exc})")

extras = sorted(p.name for p in ROOT.glob("*.wav") if p.name not in EXPECTED)
if extras:
    print("Additional WAV files:", ", ".join(extras))
if errors:
    print("\nVALIDATION FAILED")
    print("\n".join(errors))
    sys.exit(1)
print(f"\nValidated {len(EXPECTED)} synthesized WAV assets.")
