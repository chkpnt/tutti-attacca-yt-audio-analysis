#!/usr/bin/env python3
"""Dump MP4/MOV edit list (elst) entries.

Walks the box tree to moov/trak/edts/elst and prints each entry's
segment_duration (movie timescale), media_time (media timescale, signed),
and rate. A trimming edit list has media_time > 0 (samples to skip at the
start, e.g. AAC priming); media_time=0 means the edit list maps the raw
media timeline unchanged.

Usage:
    python3 dump-elst.py file.m4a [file2.mp4 ...]

Reference points (ProbeNavigator calibration):
    calibration.m4a (FFmpeg-encoded): media_time=1024 at 48 kHz -> 21.3 ms
    priming trimmed.
    yt_calibration-*.m4a (YouTube via yt-dlp): trivial edit list
    (media_time=0); the ~1600-sample AAC priming is undeclared, so all
    consumers present the raw timeline (+36.3 ms vs source PCM).
"""

import struct
import sys

CONTAINERS = {b"moov", b"trak", b"edts", b"mdia", b"minf", b"stbl", b"udta"}


def walk(data, start, end, path):
    off = start
    while off + 8 <= end:
        size, typ = struct.unpack_from(">I4s", data, off)
        hdr = 8
        if size == 1:
            size, = struct.unpack_from(">Q", data, off + 8)
            hdr = 16
        elif size == 0:
            size = end - off
        body, nxt = off + hdr, off + size
        if typ == b"elst":
            ver = data[body]
            n, = struct.unpack_from(">I", data, body + 4)
            print(f"{'/'.join(path)}/elst  version={ver} entries={n}")
            p = body + 8
            for _ in range(n):
                if ver == 1:
                    dur, mt, ri, rf = struct.unpack_from(">Qqhh", data, p)
                    p += 20
                else:
                    dur, mt, ri, rf = struct.unpack_from(">Iihh", data, p)
                    p += 12
                print(f"  segment_duration={dur}  media_time={mt}  "
                      f"rate={ri}.{rf:04x}")
        elif typ in CONTAINERS:
            walk(data, body, nxt, path + (typ.decode(),))
        off = nxt


def main():
    for path in sys.argv[1:]:
        print(f"== {path} ==")
        data = open(path, "rb").read()
        before = None
        walk(data, 0, len(data), ())


if __name__ == "__main__":
    main()
