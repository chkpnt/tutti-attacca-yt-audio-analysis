#!/usr/bin/env python3
"""Extract cue onset timestamps from ProbeNavigator calibration files.

Decodes each input with FFmpeg (any container FFmpeg reads: .wav/.m4a/.opus/
.webm/.mov/.mp4, audio-only or audio+video), finds the 1 kHz cue bursts by an
absolute-amplitude threshold criterion, and prints onset times plus deltas
against the fixture's expected cue positions.

Usage:
    python3 extract-clicks.py yt_calibration-*.m4a yt_calibration-*.webm
    python3 extract-clicks.py calibration.wav calibration.m4a calibration.opus

Reading the output: the mean offset is the constant origin shift of the file;
the spread (max-min of the per-cue deltas) exposes rate drift. The detected
onset carries a small, codec-dependent criterion bias (the first sample
crossing the threshold, not the mathematical burst start) — identical across
files encoded at the same level, so deltas between files stay comparable.
"""

import argparse
import subprocess
import sys

import numpy as np

SAMPLE_RATE = 48000
EXPECTED_CUES = [1.000, 1.310, 10.000, 30.000, 59.000]


def decode_mono(path):
    proc = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", path, "-map", "0:a:0",
         "-ac", "1", "-ar", str(SAMPLE_RATE), "-f", "f32le", "-"],
        capture_output=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.decode(errors="replace").strip())
    return np.frombuffer(proc.stdout, dtype=np.float32)


def find_onsets(pcm, threshold, min_gap_s=0.2):
    above = np.abs(pcm) > threshold
    edges = np.flatnonzero(~above[:-1] & above[1:]) + 1
    onsets = []
    last = -np.inf
    for idx in edges:
        t = idx / SAMPLE_RATE
        if t - last >= min_gap_s:
            onsets.append(t)
            last = t
    return onsets


def report(path, onsets, expected):
    print(f"== {path} ==")
    print("  onsets: " + "  ".join(f"{t:.4f}" for t in onsets))
    if expected and len(onsets) == len(expected):
        deltas = [(t - e) * 1000 for t, e in zip(onsets, expected)]
        print("  delta vs expected (ms): "
              + "  ".join(f"{d:+.1f}" for d in deltas))
        print(f"  mean offset {np.mean(deltas):+.1f} ms, "
              f"spread {max(deltas) - min(deltas):.1f} ms")
    elif expected:
        print(f"  WARNING: expected {len(expected)} cues, "
              f"found {len(onsets)} — raw onsets only")
    print()


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="+", help="audio or video files to analyse")
    ap.add_argument("--threshold", type=float, default=0.05,
                    help="absolute amplitude onset threshold (default: 0.05)")
    ap.add_argument("--expected", type=float, nargs="*", default=EXPECTED_CUES,
                    help="expected cue positions in seconds "
                         "(default: %(default)s; pass none with '--expected')")
    args = ap.parse_args()

    failed = False
    for path in args.files:
        try:
            pcm = decode_mono(path)
        except RuntimeError as exc:
            print(f"== {path} ==\n  ERROR: {exc}\n", file=sys.stderr)
            failed = True
            continue
        report(path, find_onsets(pcm, args.threshold), args.expected)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
