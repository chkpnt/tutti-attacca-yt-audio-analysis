#!/usr/bin/env python3
"""compare-drift.py — constant time offset between two audio files via cross-correlation.

Both inputs are decoded with FFmpeg (mono, 48 kHz float PCM), so containers and
codecs may differ, and FFmpeg's decode-side handling (edit lists, Opus pre-skip)
applies — the result describes the decoded presentation timelines.

The reported lag k aligns B to A:
    k > 0   B's content is k samples LATER than A's
    k < 0   B's content is k samples EARLIER than A's

Usage:
    python3 scripts/compare-drift.py A B

Examples:
    # YouTube AAC rendition vs Opus rendition (expect +36.3 ms):
    python3 scripts/compare-drift.py \
        yt-downloads/yt_calibration-wav.webm yt-downloads/yt_calibration-wav.m4a

    # corrected M4A vs Opus rendition (expect 0.0 ms):
    python3 scripts/compare-drift.py \
        yt-downloads/yt_calibration-wav.webm yt-downloads/yt_calibration-wav-corrected.m4a

Note: full-length signals are correlated in one shot via FFT, which needs
O(len(A) + len(B)) memory. For very long recordings, trim both inputs to a
representative excerpt first (e.g. ffmpeg -t 60).
"""
import subprocess
import sys

import numpy as np

RATE = 48000


def decode(path):
    p = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", str(RATE), "-f", "f32le", "-"],
        capture_output=True,
        check=True,
    )
    return np.frombuffer(p.stdout, dtype=np.float32)


def lag_samples(a, b):
    n = len(a) + len(b) - 1
    nfft = 1 << (n - 1).bit_length()
    A = np.fft.rfft(a, nfft)
    B = np.fft.rfft(b, nfft)
    r = np.fft.irfft(B * np.conj(A), nfft)  # peak at k>0: b delayed by k samples
    k = int(np.argmax(r))
    if k > nfft // 2:
        k -= nfft
    return k


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    a = decode(sys.argv[1])
    b = decode(sys.argv[2])
    k = lag_samples(a, b)
    ms = k / RATE * 1000
    if k > 0:
        relation = "later than"
    elif k < 0:
        relation = "earlier than"
    else:
        relation = "aligned with"
    print(f"{sys.argv[2]}\n  is {abs(ms):.2f} ms {relation} {sys.argv[1]}")
    print(f"  lag: {k:+d} samples @ {RATE} Hz = {ms:+.4f} ms")


if __name__ == "__main__":
    main()
