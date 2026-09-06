# Audio timeline calibration fixtures

This directory contains reproducible source fixtures for validating the time-coordinate chain used by *tutti-attacca*:

```text
known PCM timeline
  -> uploaded YouTube source video
  -> YouTube-generated AAC/M4A or Opus/WebM representation
  -> yt-dlp download
  -> sync-time edit-list correction (AAC/M4A only)
  -> Audacity timestamp authoring
  -> HTMLMediaElement.currentTime in Firefox, Chromium, and Safari
```

The purpose is to determine whether a timestamp read from a downloaded audio asset in Audacity targets the same audible instant when assigned to `HTMLMediaElement.currentTime` in a browser.

Three **master videos** were deliberately created from the same visual and PCM timeline but use different source-audio formats:

| Upload fixture | Container | Source audio codec | Why it exists |
|---|---|---|---|
| `calibration-wav.mov` | QuickTime/MOV | PCM WAV | Reference-quality upload; no lossy source-codec delay |
| `calibration-aac.mp4` | MP4 | AAC-LC | Models a creator who uploads AAC/MP4 audio |
| `calibration-opus.webm` | WebM | Opus | Models a creator who uploads Opus/WebM audio |

YouTube creates its own delivery representations after upload. The input codecs are therefore not expected to be served unchanged; the test determines whether YouTube's generated AAC/M4A and Opus/WebM timelines depend on the creator's input format.

## Repository layout

```text
.
├── README.md
├── master/                            # authoritative fixture sources (the PCM coordinate + upload masters)
│   ├── calibration.wav                # PCM master, 48 kHz mono, cues A–E
│   ├── calibration.m4a                # local AAC encode (edit-listed control)
│   ├── calibration-44k.m4a            # local AAC encode at 44.1 kHz (sample-rate probe)
│   ├── calibration.opus               # local Opus encode
│   ├── calibration-video.mp4          # visual master (white-flash track)
│   ├── calibration-wav.mov            # upload master, PCM audio
│   ├── calibration-aac.mp4            # upload master, AAC audio
│   └── calibration-opus.webm          # upload master, Opus audio
├── yt-downloads/                      # YouTube delivery assets + browser harness
│   ├── yt_calibration-{wav,aac,opus}.m4a
│   ├── yt_calibration-{wav,aac,opus}.webm
│   ├── yt_calibration-wav-corrected.m4a
│   ├── yt_calibration-*.ffprobe.txt
│   ├── measure-click.html
│   └── click-worklet.js
└── scripts/
    ├── extract-clicks.py
    ├── dump-elst.py
    └── compare-drift.py
```

Fixture-generation commands below are run inside `master/`, download commands inside `yt-downloads/`, and the analysis scripts from the repository root (they take explicit paths).

## Tools

| Tool | Purpose |
|---|---|
| `scripts/extract-clicks.py` | Offline cue-onset extraction from any audio/video file via FFmpeg decode |
| `scripts/dump-elst.py` | Dump MP4/MOV edit-list (`elst`) entries: priming-trim forensics |
| `scripts/compare-drift.py` | Constant lag between two files via cross-correlation of FFmpeg-decoded PCM (e.g. M4A vs WebM) |
| `yt-downloads/measure-click.html` + `click-worklet.js` | In-browser measurement of the `HTMLMediaElement.currentTime` at which clicks are presented |

## Fixture design

All variants originate from `master/calibration.wav`, a 60.000-second, mono, 48 kHz PCM master. It contains five 50 ms, 1 kHz sine bursts at the following exact PCM positions:

| Cue | Start time | End time |
|---|---:|---:|
| A | 1.000 s | 1.050 s |
| B | 1.310 s | 1.360 s |
| C | 10.000 s | 10.050 s |
| D | 30.000 s | 30.050 s |
| E | 59.000 s | 59.050 s |

The video is black except for a full-frame white flash during each corresponding cue interval. It is 1280×720 at 60 fps for 60 seconds.

The cue layout reveals several failure classes:

- **Constant origin offset:** every cue is displaced by the same amount.
- **Rate drift:** the offset changes from cue A through E.
- **Leading priming:** audio begins later than the visual first cue.
- **Trailing padding/end-trim discrepancy:** the final cue or total duration is wrong.
- **WebKit Ogg/Opus regression:** `HTMLMediaElement.duration` and seeks differ from the PCM/visual timeline despite valid Ogg granule positions.

The audio signal is intentionally simple. It has a sharp, high-contrast onset in Audacity's waveform/spectrogram, survives lossy re-encoding well, and avoids ambiguity from musical phrasing. The visual flashes additionally allow checking YouTube's own player timeline (A/V sync) by frame-stepping.

## Prerequisites

```bash
ffmpeg -version
ffprobe -version
python3 --version
```

Required FFmpeg capabilities:

- `libx264` for the MP4/MOV video stream;
- `libvpx-vp9` for the WebM video stream;
- `libopus` for Ogg/Opus;
- the native `aac` encoder;
- PCM (`pcm_s24le`).

`drawtext` is intentionally **not** required. Some macOS FFmpeg builds omit it because they were built without FreeType/font-rendering support. The fixture uses visual flashes instead of a text timecode overlay.

On Apple Silicon Homebrew, the FFmpeg binary is commonly `/opt/homebrew/bin/ffmpeg`. Check that the capabilities exist before generating assets:

```bash
ffmpeg -hide_banner -encoders | grep -E 'libx264|libvpx-vp9|libopus|aac|pcm_s24le'
```

## Generate fixture sources

Run all commands in this section inside `master/`.

### PCM master

The master contains audio only:

```bash
ffmpeg -y \
  -f lavfi \
  -i "aevalsrc=0.8*sin(2*PI*1000*t)*(between(t\\,1\\,1.05)+between(t\\,1.31\\,1.36)+between(t\\,10\\,10.05)+between(t\\,30\\,30.05)+between(t\\,59\\,59.05)):s=48000:d=60" \
  -ac 1 \
  -ar 48000 \
  -c:a pcm_s24le \
  calibration.wav
```

Verify it before encoding anything else:

```bash
ffprobe -v error \
  -show_entries format=duration:stream=codec_name,sample_rate,channels \
  -of default=nw=1 \
  calibration.wav
```

Expected essentials:

```text
codec_name=pcm_s24le
sample_rate=48000
channels=1
duration=60.000000
```

Open `calibration.wav` in Audacity and confirm that cues A–E begin at the declared positions. This WAV is the authoritative PCM coordinate system.

### AAC and Opus sources

Generate the delivery-format source assets directly from the PCM master. Do not generate AAC from Opus or Opus from AAC: that would add an unnecessary second lossy generation and spoil the comparison.

```bash
ffmpeg -y -i calibration.wav \
  -c:a aac -b:a 192k \
  calibration.m4a

ffmpeg -y -i calibration.wav \
  -c:a libopus -b:a 160k \
  calibration.opus
```

A 44.1 kHz AAC variant serves as the probe that separates sample-rate-dependent presentation offsets from YouTube-rendition-specific ones (YouTube's AAC rendition is always 44.1 kHz):

```bash
ffmpeg -y -i calibration.wav \
  -ar 44100 -c:a aac -b:a 192k \
  calibration-44k.m4a
```

Verify them:

```bash
for f in calibration.wav calibration.m4a calibration.opus calibration-44k.m4a; do
  echo "=== $f ==="
  ffprobe -v error \
    -show_entries format=format_name,duration:stream=codec_name,sample_rate,channels \
    -of default=nw=1 \
    "$f"
done
```

Expected output, verified with this exact pipeline:

```text
=== calibration.wav ===
codec_name=pcm_s24le
sample_rate=48000
channels=1
format_name=wav
duration=60.000000
=== calibration.m4a ===
codec_name=aac
sample_rate=48000
channels=1
format_name=mov,mp4,m4a,3gp,3g2,mj2
duration=60.000000
=== calibration.opus ===
codec_name=opus
sample_rate=48000
channels=1
format_name=ogg
duration=60.006500
```

The reported durations differ by container accounting, not generation failure:

- `calibration.wav` has no priming and is exact by construction.
- `calibration.m4a` is exact because FFmpeg writes AAC encoder priming as an MP4 edit list and applies that list when it demuxes the file.
- `calibration.opus` includes the libopus pre-skip of 312 samples in the reported Ogg granule span: \(312 / 48000 = 6.5\) ms. Some FFmpeg versions expose this instead as `start_time=0.006500`. A conforming decoder removes the pre-skip; decoding back to PCM yields exactly 60.000 s and starts content at sample zero.

### Visual master

Create the visual stream once. It uses a white full-frame flash at each audio cue and needs no font support:

```bash
ffmpeg -y \
  -f lavfi \
  -i "color=c=black:s=1280x720:r=60:d=60" \
  -vf "geq=r='255*(between(T\\,1\\,1.05)+between(T\\,1.31\\,1.36)+between(T\\,10\\,10.05)+between(T\\,30\\,30.05)+between(T\\,59\\,59.05))':g='r(X,Y)':b='r(X,Y)'" \
  -an \
  -c:v libx264 -pix_fmt yuv420p \
  -movflags +faststart \
  calibration-video.mp4
```

Check the video stream:

```bash
ffprobe -v error \
  -show_entries format=duration:stream=codec_name,width,height,r_frame_rate \
  -of default=nw=1 \
  calibration-video.mp4
```

Expected essentials:

```text
codec_name=h264
width=1280
height=720
r_frame_rate=60/1
duration=60.000000
```

### Master videos

#### WAV/PCM source: MOV

MOV accepts PCM and H.264. Stream-copy both inputs:

```bash
ffmpeg -y \
  -stream_loop -1 -i calibration-video.mp4 \
  -i calibration.wav \
  -map 0:v:0 -map 1:a:0 \
  -c:v copy -c:a copy \
  -shortest \
  calibration-wav.mov
```

#### AAC source: MP4

MP4 accepts the H.264 visual stream and AAC audio stream. Stream-copy both:

```bash
ffmpeg -y \
  -stream_loop -1 -i calibration-video.mp4 \
  -i calibration.m4a \
  -map 0:v:0 -map 1:a:0 \
  -c:v copy -c:a copy \
  -shortest \
  -movflags +faststart \
  calibration-aac.mp4
```

#### Opus source: WebM

WebM does not support H.264, so the video is encoded to VP9. The Opus audio is stream-copied:

```bash
ffmpeg -y \
  -stream_loop -1 -i calibration-video.mp4 \
  -i calibration.opus \
  -map 0:v:0 -map 1:a:0 \
  -c:v libvpx-vp9 -crf 32 -b:v 0 \
  -c:a copy \
  -shortest \
  calibration-opus.webm
```

Validate all masters before upload:

```bash
for f in calibration-wav.mov calibration-aac.mp4 calibration-opus.webm; do
  echo "=== $f ==="
  ffprobe -v error \
    -show_entries format=format_name,duration:stream=index,codec_type,codec_name,sample_rate,channels,r_frame_rate \
    -of default=nw=1 \
    "$f"
done
```

Expected structure:

| File | Video | Audio |
|---|---|---|
| `calibration-wav.mov` | H.264, 1280×720, 60 fps | PCM 24-bit, 48 kHz mono |
| `calibration-aac.mp4` | H.264, 1280×720, 60 fps | AAC, 48 kHz mono |
| `calibration-opus.webm` | VP9, 1280×720, 60 fps | Opus, 48 kHz mono |

For an A/V sanity check, play each master locally. At every white flash, the 1 kHz beep must begin together. A phone slow-motion recording is adequate to notice a gross muxing error, though not for the primary timestamp measurement.

Generate checksums after final verification (inside `master/`):

```bash
shasum -a 256 \
  calibration.wav calibration.m4a calibration.opus calibration-44k.m4a \
  calibration-video.mp4 \
  calibration-wav.mov calibration-aac.mp4 calibration-opus.webm \
  > SHA256SUMS
```

## YouTube uploads

The three master videos were published as unlisted YouTube videos on 2026-09-02:

| Master video | Source audio | YouTube video |
|---|---|---|
| `calibration-wav.mov` | PCM | [pZg-6ptiri4](https://youtu.be/pZg-6ptiri4) |
| `calibration-aac.mp4` | AAC-LC | [DZFI8VRo8EQ](https://youtu.be/DZFI8VRo8EQ) |
| `calibration-opus.webm` | Opus | [yFGvJwqGYL8](https://youtu.be/yFGvJwqGYL8) |

If a master changes, upload a new unlisted video, wait for processing to complete, and update the table before repeating the retrieval and measurement steps.

## Download delivery audio

Run the commands in this section inside `yt-downloads/`.

List formats for an upload when needed:

```bash
yt-dlp -F "https://youtu.be/pZg-6ptiri4"
```

Download both delivery formats for each upload. The result name expresses the **source upload audio** followed by the delivery container: `.m4a` for AAC and `.webm` for Opus.

```bash
while read -r id src; do
  yt-dlp \
    -f 'bestaudio[ext=m4a][acodec^=mp4a]/bestaudio[ext=m4a]' \
    -o "yt_calibration-${src}.%(ext)s" \
    "https://youtu.be/${id}"
  yt-dlp \
    -f 'bestaudio[ext=webm][acodec=opus]' \
    -o "yt_calibration-${src}.%(ext)s" \
    "https://youtu.be/${id}"
done <<'EOF'
pZg-6ptiri4 wav
DZFI8VRo8EQ aac
yFGvJwqGYL8 opus
EOF
```

Expected downloads:

```text
yt_calibration-wav.m4a    yt_calibration-wav.webm
yt_calibration-aac.m4a    yt_calibration-aac.webm
yt_calibration-opus.m4a   yt_calibration-opus.webm
```

If a file gets a different extension, the selection fell back; inspect it with `yt-dlp -F` rather than accepting a misleading name.

Additionally, the corrected M4A variant is produced from the downloaded WAV-arm M4A (see "Correcting the YouTube M4A timeline" below):

```text
yt_calibration-wav-corrected.m4a
```

Persist `ffprobe` output for each downloaded delivery asset:

```bash
for f in yt_calibration-*.m4a yt_calibration-*.webm; do
  ffprobe -hide_banner "$f" 2>&1 | tee "$f.ffprobe.txt"
done
```

### Observed delivery formats

All three YouTube M4A renditions were equivalent in the relevant properties:

```text
container: mov,mp4,m4a,3gp,3g2,mj2
codec:     AAC-LC
rate:      44100 Hz
channels:  stereo
bitrate:   about 127 kb/s
duration:  60.070 s
encoder:   Lavf63.1.101 / Google Inc.
```

All YouTube WebM renditions were Opus at 48 kHz stereo, with container durations of 60.021 s (WAV and AAC uploads) and 60.041 s (Opus upload). These raw container-duration differences are end-of-stream granule accounting and do not correspond to cue-time drift.

The corrected M4A reports `duration: 60.034 s` in ffprobe/Firefox/Chromium (60.070 s minus the 36.3 ms priming moved out of the presentation timeline). Safari reports 60.022 s for both the uncorrected and the corrected file — it derives the element duration from the raw media span with its own end-trim, not from the edit list (cosmetic; the origin mapping does follow the edit list, see "Browser results"). The corrected file's major_brand changes from `isom` to `M4A` — an artifact of FFmpeg's default branding for the `.m4a` extension, cosmetically avoidable with `-brand isom`.

## Raw decode analysis

`extract-clicks.py` decodes audio or video inputs through FFmpeg to mono 48 kHz float PCM, detects each calibration-tone onset, and compares it with the source cue schedule. The 44.1 kHz YouTube M4A rendition is intentionally resampled during analysis; this is necessary to compare all sources in a shared sample coordinate and does not create time drift.

Run from the repository root:

```bash
python3 scripts/extract-clicks.py \
  master/calibration.wav master/calibration.m4a master/calibration.opus

python3 scripts/extract-clicks.py \
  yt-downloads/yt_calibration-*.m4a yt-downloads/yt_calibration-*.webm
```

### Observed raw-decode results

| Assets | Cue offset vs PCM master | Cue-to-cue spread | Result |
|---|---:|---:|---|
| `master/calibration.wav` | 0.0 ms | 0.0 ms | Exact PCM reference |
| `master/calibration.m4a` | 0.0 ms | 0.0 ms | Local FFmpeg AAC edit-list handling is aligned |
| `master/calibration.opus` | 0.0 ms | 0.0 ms | Local Ogg/Opus pre-skip/end trimming is aligned |
| `master/calibration-44k.m4a` | 0.0 ms (by construction) | — | Local 44.1 kHz AAC; local encodes are source-aligned (edit list) |
| `yt_calibration-{wav,aac,opus}.m4a` | +36.3 ms | 0.0 ms | YouTube AAC raw decode has a deterministic leading offset |
| `yt_calibration-{wav,aac,opus}.webm` | 0.0 ms | 0.0 ms | YouTube Opus raw decode is aligned |
| `yt_calibration-wav-corrected.m4a` | 0.0 ms | 0.0 ms | Corrected rendition decodes source-aligned (edit list applied by FFmpeg) |

The +36.3 ms offset is constant at all five cues (1.000, 1.310, 10.000, 30.000, 59.000 s) and across all three upload-source codecs. At 44.1 kHz it is approximately 1600 samples, consistent with AAC priming/encoder-delay accounting:

\[
0.0363\text{ s} \times 44100\text{ Hz} \approx 1601\text{ samples}
\]

Therefore YouTube does **not** stretch AAC relative to Opus and there is no rate drift. It places the decoded AAC musical content at a stable later origin. The creator's uploaded audio codec—PCM, AAC, or Opus—does not change that behaviour.

## Container forensics (edit lists)

`dump-elst.py` walks the MP4 box tree and prints the edit-list entries that decide whether AAC priming is trimmed from the presentation timeline.

```bash
python3 scripts/dump-elst.py \
  master/calibration.m4a \
  yt-downloads/yt_calibration-wav.m4a \
  yt-downloads/yt_calibration-wav-corrected.m4a
```

Measured:

| File | `elst` entry | Effect |
|---|---|---|
| `master/calibration.m4a` | `segment_duration=2880000` (60.000 s at 48 kHz movie timescale), `media_time=1024`, `rate=1` | Presentation starts 1024 samples (21.3 ms) into the media → priming trimmed, source-aligned |
| `yt_calibration-wav.m4a` | `segment_duration=2649088` (60.07002 s at 44.1 kHz), `media_time=0`, `rate=1` | Identity mapping of the full raw span → priming is part of the timeline |
| `yt_calibration-wav-corrected.m4a` | `segment_duration=2647488` (60.0337 s at 44.1 kHz = 2649088 − 1600), `media_time=1600`, `rate=1` | Priming trimmed → source-aligned (confirmed 2026-09-06; matches the value predicted from the simulated fixture) |

Supporting checks on the YouTube M4A:

```bash
ffprobe -v error -ignore_editlist 1 \
  -show_entries format=duration -of default=nw=1 yt-downloads/yt_calibration-wav.m4a
# duration=60.070023  (unchanged — the edit list trims nothing)
ffprobe -v error -show_entries format_tags -of default=nw=1 yt-downloads/yt_calibration-wav.m4a
# only major_brand/minor_version/compatible_brands/encoder — no iTunSMPB
```

Control on the local M4A: `ffprobe` reports 60.000000 by default and exposes the raw span (60.000 s + 21.3 ms priming + padding) with `-ignore_editlist 1`.

Interpretation: the YouTube rendition carries **undeclared priming** — no ISO edit-list trim, no Apple `iTunSMPB`. Every consumer therefore presents the raw timeline, which is why ffprobe, Audacity, and all four browser/engine combinations agree on the +36.3 ms coordinate. The trivial `media_time=0` edit list is the fingerprint of yt-dlp's stream-copy remux: the muxer never decodes, so it never learns the encoder's `initial_padding` and cannot write a trimming edit list. A side benefit of undeclared priming is stability: there is no metadata for a future browser or ffmpeg version to start interpreting differently.

## Correcting the YouTube M4A timeline

The undeclared priming can be moved out of the presentation timeline at sync time — **without re-encoding** — by making FFmpeg's MP4 muxer write the missing trimming edit list itself. Run from the repository root:

```bash
ffmpeg -itsoffset -0.0362812 \
  -i yt-downloads/yt_calibration-wav.m4a \
  -c:a copy \
  yt-downloads/yt_calibration-wav-corrected.m4a
```

Mechanism: `-itsoffset` shifts the input timestamps; the first packet lands at a negative PTS (−1600 samples at 44.1 kHz), and the MP4 muxer — which cannot store negative media times — re-bases the media timeline and records the shift as an edit list (`elst` with `media_time=1600`; confirmed with `dump-elst.py` on the real corrected file, 2026-09-06). The AAC bitstream is copied unchanged (`-c:a copy`); only container metadata is added. The result carries exactly the same edit-list structure that makes the locally encoded `master/calibration.m4a` source-aligned everywhere — just with YouTube's 1600-sample priming instead of FFmpeg's 1024. The mechanism was first validated on a simulated fixture (undeclared priming → muxer writes the trimming edit list; decode-aligned; bitstream MD5-identical).

The offset constant is 1600 samples at 44.1 kHz = 36.281 ms (`-itsoffset -0.0362812`); cross-correlation against the Opus rendition (`scripts/compare-drift.py`) measured 36.292 ± 0.02 ms. It is a global property of YouTube's AAC rendition: the same +36.3 ms was measured on an unrelated real piece (video `xX1Y0cxstBw`, outside this fixture set). It must **not** be applied to locally encoded files or to a last-resort local transcode of a YouTube track, both of which are already source-aligned.

Verification of the corrected fixture:

- `dump-elst.py` (2026-09-06): `segment_duration=2647488`, `media_time=1600`, `rate=1` — the expected trimming edit list.
- `extract-clicks.py` (2026-09-03): onsets 1.0000 / 1.3100 / 10.0000 / 30.0000 / 59.0000 s — all five cues at **+0.0 ms**, spread 0.0 ms. FFmpeg applies the new edit list on decode.
- Audacity (2026-09-03): imported side by side with `master/calibration.m4a`, all peaks align exactly; the corrected file displays 34 ms longer (60.034 vs 60.000 s) because YouTube's larger end padding survives in the raw span — cosmetic.
- Browsers (2026-09-06, harness v3): Firefox +0.7 ms, Chromium +1.4 ms, Safari ≈ −7 ms vs the WAV control, each constant from click A to click C — the remaining per-engine constant is the 44.1 kHz presentation shift (see "Browser results"), not a correction error.

Guard for the pipeline: after correcting a fresh download, `extract-clicks.py` must read 0.0 ms — and a cross-correlation of the fresh download against the kept Opus/WebM authoring reference (`scripts/compare-drift.py`) must read ≈ 36.3 ms before correction and 0.0 ms after. If a future YouTube download measures an offset different from +36.3 ms, YouTube changed its encoding pipeline and the constant must be re-derived.

## Browser measurement harness

The browser harness lives in `yt-downloads/` next to the delivery assets and contains two files that must be served together over HTTP:

```text
yt-downloads/measure-click.html
yt-downloads/click-worklet.js
```

`measure-click.html` (v3, 2026-09-06) measures the listed files sequentially. One **shared** `AudioContext` and one `AudioWorkletNode` serve the whole run (the detector state is reset per file via a port message); per file only a fresh `<audio>` element and `MediaElementAudioSourceNode` are created. The full capture is 11 s, so clicks A (1.000 s), B (1.310 s) and C (10.000 s) are measured in one pass; a quick mode (1.8 s, A/B only) is available via checkbox.

`click-worklet.js` detects the first sample above the calibration threshold in the AudioWorklet rendering thread. It reports the absolute `currentFrame` for each click, avoiding the capture-start / ScriptProcessor scheduling errors encountered by earlier test pages.

The harness maps a worklet frame to the media-element timeline by collecting steady-state pairs of:

```js
[ctx.getOutputTimestamp().contextTime, audio.currentTime]
```

Per file it reports the clock-pair MAD and the early→late drift of the mapping; each click is mapped with the clock pairs collected around it (±0.75 s window), so a one-time mapping jump inside a file does not corrupt all of its click times. A summary block lists per-file click-A/C times, deltas vs the WAV control, MAD, drift, and adaptive flags (a file is flagged only if it exceeds twice the run's own median, minimum 3 ms).

Why a shared context (v2 lesson): with per-file `AudioContext`s, each context's output path added its own mapping variance, and the context churn made Safari 26.6 stop the loop after ~2 files. The shared context cured both (full runs on all engines; Safari per-file MAD 0.7–0.9 ms).

iOS autoplay: transient activation expires across awaits, so the first file's `play()` is issued synchronously inside the click handler; if `play()` is still rejected (`NotAllowedError`), the run pauses and shows a "tap to continue" button for a fresh gesture (on iOS 26.6 each file needs one tap).

Known engine quirks of the harness itself: Chromium may start files at `currentTime=0` instead of the seek target (harmless — the mapping is position-independent and all clicks still fall inside the capture window); Firefox's clock reporting wobbles ±10.7 ms on every file (benign quantization, absorbed by the median).

### Run the harness

Serve the **repository root**, so both the harness in `yt-downloads/` and the local controls in `master/` are reachable:

```bash
python3 -m http.server 8000    # from the repository root
```

Open `http://localhost:8000/yt-downloads/measure-click.html` and press **Measure all**. A user gesture is required to resume the `AudioContext` and start media playback.

File names in the textarea resolve relative to the page URL, so the delivery files need no prefix and the local controls use `../master/`. For a compact control run, replace the textarea file list with:

```text
../master/calibration.wav
../master/calibration.m4a
yt_calibration-wav.m4a
yt_calibration-wav-corrected.m4a
yt_calibration-wav.webm
```

The worklet output is connected to an intentionally tiny non-zero gain (`0.00001`). A literal zero-gain branch can be optimized away; the chosen value keeps the graph live while remaining effectively inaudible. (Exception: the first file may be briefly audible on iOS, where playback starts inside the user gesture before the tap connects.) Gain staging differs between engines: Safari may make the calibration tones audible where Firefox and Chromium stay silent. Audibility does not affect the measurement.

### Secure contexts and iOS

AudioWorklet requires a secure context. `http://localhost` qualifies; a plain HTTP LAN URL (e.g. `http://192.168.x.x:8000` on a phone) does **not** and fails with:

```text
ERROR: undefined is not an object (evaluating 'ctx.audioWorklet.addModule')
```

For iOS testing, serve the harness over HTTPS — a locally trusted certificate or a tunnel such as `cloudflared tunnel --url http://localhost:8000` — then open `https://<host>/yt-downloads/measure-click.html`.

### Measurement interpretation

Absolute click values contain a per-file clock-mapping bias; the meaningful result is the difference between files. First check the run's stability: the MAD column should be uniform across files (Firefox shows a constant ~10.7 ms quantization wobble on every file — benign; Safari ~0.8 ms; Chromium ~0–0.9 ms), and no file should be flagged in the summary.

| Observation | Meaning |
|---|---|
| Local `calibration.wav` and `calibration.m4a` agree | Local AAC edit-list/presentation accounting is aligned in that engine |
| A file is flagged UNSTABLE/DRIFT while others are clean | File-specific presentation problem in that engine — distrust that file's absolute values |
| YouTube M4A later than local controls by about +36–38 ms | Engine exposes the YouTube M4A raw AAC coordinate |
| All 44.1 kHz files (YouTube M4A *and* `calibration-44k.m4a`) share a constant shift vs the 48 kHz controls | Engine's 44.1 kHz presentation constant: Firefox +0.7 ms, Chromium +1.5 ms, Safari ≈ −7 ms |
| WebM/Opus ~+7.5 ms vs WAV in Firefox, ±0 in Chromium | Opus element-path offset (pre-skip class); production-irrelevant today (YouTube mode = IFrame player, audio mode = M4A); relevant if Opus ever ships |
| Corrected M4A earlier than the uncorrected one by ~36.3 ms | The engine honors the sync-time edit-list correction |
| A B→C spacing near 8.733 s on a YouTube M4A in Safari | One-off mid-run mapping jump (recurs sporadically on uncorrected YouTube files); the windowed per-click mapping absorbs it — distrust that file's C reading, A readings remain valid |
| `peak=0.00000` while playback is audible | WebKit silent-tap limitation: the media element's audio does not reach `createMediaElementSource` for that codec; a harness limitation, not a playback defect |

## Browser results

### Firefox

Firefox 155 macOS, full run with harness v3 (2026-09-06, shared 48 kHz AudioContext; MAD 10.7 ms on every file = Firefox's clock-reporting quantization, absorbed by the median; identical values in the 2026-09-02 v1 run and the v3 repetition):

| File group | Click A | Click C | vs WAV | Drift |
|---|---:|---:|---:|---:|
| `yt_calibration-*.m4a` (all three arms) | 1.0376 s | 10.0376 s | **+37.0 ms** | 0.0 ms |
| `yt_calibration-*.webm` (all three arms) | 1.0081 s | 10.0081 s | **+7.5 ms** | 0.0 ms |
| `yt_calibration-wav-corrected.m4a` | 1.0013 s | 10.0013 s | **+0.7 ms** | 0.0 ms |
| `master/calibration-44k.m4a` | 1.0013 s | 10.0013 s | **+0.7 ms** | 0.0 ms |
| `master/calibration.wav` | 1.0006 s | 10.0006 s | baseline | 0.0 ms |
| `master/calibration.m4a` | 1.0006 s | 10.0006 s | 0.0 ms | 0.0 ms |

- The uncorrected YouTube M4A presents the raw coordinate (+37.0 ms), the corrected file is aligned within +0.7 ms — at click C as well, so there is no startup settling in Firefox.
- Firefox's 44.1 kHz presentation constant is +0.7 ms (the local 44.1 kHz encode and the corrected file show it identically).
- The WebM/Opus element path presents a constant **+7.5 ms** vs the WAV/M4A paths (all arms, all runs — Opus element-path offset; the offline decode of the same files is exact). Production-irrelevant today; relevant if Opus ever ships.
- Spacings are exact (A→B 0.310000 s, B→C 8.690000 s).

### Chromium

Chromium 150 macOS, full run with harness v3 (2026-09-06; MAD 0.0–0.9 ms, drift ≤ 0.2 ms — the cleanest engine). Chromium started all files at `currentTime=0.0000` instead of the 0.5 s seek target; harmless, the mapping is position-independent:

| File group | Click A | Click C | vs WAV |
|---|---:|---:|---:|
| `yt_calibration-*.m4a` (all three arms) | 1.0649–1.0652 s | 10.0650–10.0651 s | **+37.6…+37.9 ms** |
| `yt_calibration-*.webm` (all three arms) | 1.0273 s | 10.0271–10.0273 s | **−0.1…0.0 ms** |
| `yt_calibration-wav-corrected.m4a` | 1.0287 s | 10.0288 s | **+1.4 ms** |
| `master/calibration-44k.m4a` | 1.0289 s | 10.0287 s | **+1.6 ms** |
| `master/calibration.wav` | 1.0273 s | 10.0273 s | baseline |
| `master/calibration.m4a` | 1.0273 s | 10.0273 s | −0.1 ms |

Chromium matches Firefox on the raw coordinate (+37.7 ms, consistent with the +37.6–37.8 ms of the 2026-09-02 v1 run), presents the corrected file at +1.4 ms (its 44.1 kHz constant is +1.5 ms), and — unlike Firefox — has no Opus element-path offset (WebM at ±0).

### Safari macOS

M4A measurements across two sessions (2026-09-03, older Safari, harness v1):

| File | Run 1 click A | Run 2 click A | Element duration |
|---|---:|---:|---:|
| `calibration.wav` | 0.9017 s | 0.9099 s | 60.000 s |
| `calibration.m4a` | — | 0.9050 s | 59.977 s |
| `yt_calibration-wav.m4a` | 0.9378 s | 0.9449 s | 60.022 s |
| `yt_calibration-aac.m4a` | 0.9315 s | 0.9399 s | 60.022 s |
| `yt_calibration-opus.m4a` | 0.9392 s | 0.9340 s | 60.022 s |

Relative to the same-run WAV control, the YouTube M4A clicks sit +35…+37 ms later — matching the offline +36.3 ms value. Safari's reduced M4A element durations (60.022/59.977 s) are end-side accounting, not an origin shift (proof: the local M4A aligns with the WAV control despite its trimmed duration).

Safari macOS 26.6, full runs with harness v3 (2026-09-06; the loop survived all files, per-file MAD 0.7–1.4 ms). Two runs:

| File | A−WAV (run 1) | A−WAV (run 2) | Notes |
|---|---:|---:|---|
| `master/calibration.m4a` (48 kHz) | −0.3 ms | −0.5 ms | stable |
| `master/calibration-44k.m4a` | +8.8 ms | +8.8 ms (A); C off by −12 ms, A→B spacing broken in run 2 | unstable on macOS |
| `yt_calibration-*.m4a` (uncorrected) | +28.7…+34.2 ms | +29.2…+31.6 ms | ≈ 36.3 − 7.3 |
| `yt_calibration-wav-corrected.m4a` | −7.1 ms (C: −7.5) | −4.5 ms (C: −9.5) | edit-list shift exact: 35.8–36.0 ms vs uncorrected |

Findings:

- **Safari honors the edit list exactly** (uncorrected↔corrected = 35.8–36.0 ms against the container's 36.3 ms).
- **Safari's 44.1 kHz presentation constant is ≈ −7 ms**: all YouTube M4A files (corrected and uncorrected) sit ~7 ms below the offline expectation relative to the 48 kHz controls. The local 44.1 kHz probe shows the same class of behavior (see iOS for the clean version), so the shift is sample-rate-dependent, not YouTube-rendition-specific. The 2026-09-03 runs did not show it on macOS (yt−WAV = +35…+37) but did on iOS (+29.7) — so it arrived on macOS with 26.6 and predates 26.6 on iOS.
- Safari still has sporadic mid-run mapping jumps (run 2: the 44k local's A→B spacing collapsed to 0.293 s; the corrected file logged a −124 ms early→late drift while keeping A and C self-consistent via the windowed mapping; the uncorrected files occasionally glitch click C to B→C = 8.733 s). These are presentation/reporting hiccups of the engine, not file defects — the same files measure cleanly in Firefox/Chromium and in FFmpeg decode.
- Safari reports 60.022 s for all YouTube M4A files (including the corrected one) — duration derives from the raw media span with Safari's own end-trim, not from the edit list (cosmetic).

WebM/Opus in Safari: the media element's output does not reach the Web Audio tap (silent tap: `peak=0.00000` while clicks are audible) — a harness limitation, not a playback defect; element durations are correct. This confirms that WebKit bug 293310 is specific to the **Ogg** container. Seek/currentTime accuracy for WebM/Opus in Safari is not measurable with this harness until the silent tap is fixed — that measurement is the remaining gate for shipping Opus in dist again.

### Safari iOS

Measured 2026-09-03 over HTTPS, older iOS, harness v1:

| File | Click A | Element duration | Difference to WAV |
|---|---:|---:|---:|
| `calibration.wav` | 0.8985 s | 60.000 s | baseline |
| `calibration.m4a` | 0.8985 s | 59.977 s | **+0.0 ms** |
| `yt_calibration-*.m4a` (all arms) | 0.9282–0.9284 s | 60.022 s | **+29.7–29.9 ms** |

Consistent with the offline +36.3 ms offset minus the ~7 ms 44.1 kHz presentation shift (which therefore predates 26.6 on iOS).

Safari iOS 26.6, full run with harness v3 (2026-09-06; one "tap to continue" per file, per-file MAD 0.7–0.8 ms):

| File | Click A | Click C | A−WAV | Drift |
|---|---:|---:|---:|---:|
| `master/calibration.wav` | 0.8993 s | 9.9008 s | baseline | −0.4 ms |
| `master/calibration.m4a` (48 kHz) | 0.8996 s | 9.8983 s | **+0.3 ms** | −0.5 ms |
| `master/calibration-44k.m4a` | 0.8926 s | 9.8914 s | **−6.7 ms** | −0.9 ms |
| `yt_calibration-wav.m4a` | 0.9338 s | 9.9762 s | +34.5 ms | −0.1 ms |
| `yt_calibration-aac.m4a` | 0.9284 s | 9.9276 s | +29.1 ms | −0.8 ms |
| `yt_calibration-opus.m4a` | 0.9339 s | 9.9763 s | +34.6 ms | −0.9 ms |
| `yt_calibration-wav-corrected.m4a` | 0.8926 s | 9.8911 s | **−6.7 ms** | −0.7 ms |

The clean proof that the shift is sample-rate-dependent: the local 44.1 kHz encode and the corrected YouTube file land on identical values (−6.7 ms at A, ≈−9.5 at C). Two uncorrected arms show the sporadic click-C glitch (B→C = 8.733 s); the corrected file and the local files are clean. The corrected file is exactly as stable as the local controls on iOS 26.6.

## Conclusions

### YouTube delivery timing

- YouTube's output timing is independent of whether the source upload used PCM, AAC, or Opus.
- YouTube WebM/Opus decodes at the source cue positions in FFmpeg analysis.
- YouTube M4A/AAC decodes with a fixed +36.3 ms content offset in FFmpeg/Audacity-like raw decode analysis.
- The AAC offset is constant from 1 s to 59 s; it is priming/origin accounting, not stretching or rate drift.
- The offset is a property of **YouTube's** AAC rendition, not of AAC/MP4 in general: the locally encoded `master/calibration.m4a` (FFmpeg edit list, `media_time=1024`) presents source-aligned in every engine tested.
- The YouTube M4A declares no trim signaling at all (identity edit list, no `iTunSMPB`), so the raw coordinate is the only coordinate any consumer can present — the behaviour cannot silently change due to metadata-interpretation differences.
- The missing trim can be restored losslessly at sync time: a stream copy with `-itsoffset -0.0362812` makes the muxer write an edit list with `media_time=1600` (confirmed by `dump-elst.py`), after which the M4A presents source-aligned in FFmpeg decode, Audacity, and the browser element.

### Browser timing (verified 2026-09-02…06)

| Engine / platform | Local M4A (48k) vs WAV | 44.1 kHz constant (probe) | YouTube M4A vs control | Corrected M4A vs control |
|---|---:|---:|---:|---:|
| FFmpeg/Audacity decode | 0.0 ms | 0.0 ms | +36.3 ms (exact) | 0.0 ms (exact) |
| Firefox 155 macOS | 0.0 ms | +0.7 ms | +37.0 ms | **+0.7 ms** (A and C, stable) |
| Chromium 150 macOS | −0.1 ms | +1.5 ms | +37.7 ms | **+1.4 ms** (A and C, stable) |
| Safari macOS 26.6 | −0.4 ms | ≈ −7 ms (noisy run) | +29…+34 ms | **≈ −7 ms** (edit-list shift exact) |
| Safari iOS 26.6 | +0.3 ms | −6.7 ms | +29…+35 ms | **−6.7 ms** (A), −9.7 ms (C), stable |

- All engines present the uncorrected YouTube M4A in its raw-decoded coordinate, modulo their 44.1 kHz presentation constant.
- All engines present locally encoded, edit-listed AAC source-aligned (modulo the same constant). The corrected YouTube M4A behaves exactly like a local encode in every engine — which is the point of the correction.
- Every engine has a small constant presentation offset for 44.1 kHz content (resample-path class): Firefox +0.7 ms, Chromium +1.5 ms, Safari ≈ −7 ms. These are constant per engine, apply to all 44.1 kHz files equally (corrected or not), and stay within the app's 0.01 s resolution budget — no runtime compensation is warranted.
- Safari sporadically jumps its clock mapping mid-run (the 8.733 s click-C glitch on uncorrected YouTube files; one −124 ms drift event); the harness's windowed per-click mapping keeps A and C self-consistent through such jumps.
- No engine rescales or drifts files systematically: click spacings are preserved.
- Ogg/Opus remains broken in Safari per WebKit bug 293310 (scaled duration/timeline), reproduced independently with a real recording; the defect is specific to the Ogg container.

### Timestamp authoring policy (final)

1. **Canonical coordinate: the source PCM timeline.** It is presented identically by the uploaded video (and hence the YouTube IFrame player, which keeps its Opus audio rendition in A/V sync with the video track), by YouTube's Opus/WebM download, by locally encoded files, and by the corrected YouTube M4A. Marks authored against any of these artifacts are mutually valid without conversion. Marks read from an *uncorrected* YouTube M4A sit +36.3 ms late relative to source and would need `t_src = t_m4a − 0.0363`; the pipeline avoids that case by correcting the artifact instead.
2. **YouTube pieces: keep two local files per piece, ship one.** `sync-media` downloads both renditions: the Opus/WebM (itag 251) and the AAC/M4A (itag 140), and corrects the M4A at sync time (`ffmpeg -itsoffset -0.0362812 -i <download>.m4a -c:a copy audio/<key>.m4a`; verify with `scripts/dump-elst.py` (`media_time=1600`) and `scripts/extract-clicks.py` (0.0 ms)). The layout in `audio/` is `<key>.webm` + `<key>.m4a`: the WebM is the **authoring reference** — YouTube's highest-quality audio track, source-aligned without any processing — and doubles as the cross-correlation baseline for the pipeline guard; the corrected M4A is the **playback artifact** and the only file that ships (the staging/bundle step must filter by extension: `<key>.m4a` + peaks JSON into `dist-audio/`, never the `.webm`). **Author timestamps against the WebM in Audacity**; use the corrected M4A when verifying how a mark plays. Legacy marks authored against Opus artifacts are already source-aligned and remain valid unchanged.
3. Record which artifact and coordinate system a piece's marks belong to in the piece JSON5 (see the `authoring` provenance object in the piece format spec), so future format changes remain documented constant shifts rather than archaeology.
4. Ogg/Opus remains disabled for production on WebKit (bug 293310). The Opus pipeline may be re-evaluated when Safari (a) reports a correct `HTMLMediaElement.duration` and correct seeks for the Ogg/Opus fixture, or — for shipping Opus-in-**WebM** via the element — (b) once the silent-tap limitation is resolved and the harness can verify WebM/Opus seek and `currentTime` accuracy in Safari. Until then, M4A is the shipped format.
5. The +36.3 ms offset and its correction are specific to YouTube's AAC rendition. Own recordings encoded locally with FFmpeg (`media-in` pipeline) are source-aligned in all engines and need no correction.
6. The same piece JSON drives both player modes, and both are now source-aligned: the YouTube IFrame player via its Opus rendition and A/V sync, the audio mode via the corrected M4A. The only residuals are the documented per-engine 44.1 kHz presentation constants (worst case ≈ −7 ms on Safari — constant, sub-frame at the typical 25 fps of score videos, and inside the 0.01 s budget), so the player needs no runtime offset or browser detection.

MP4/AAC is the canonical **shipping format**; Opus/WebM is kept locally as the authoring reference and guard baseline. The M4A's only timing deviation — the constant, measurable, well-understood +36.3 ms YouTube rendition offset — is corrected once at sync time by a lossless edit-list remux, so JSON timestamps, precomputed peaks, Audacity authoring, and both player modes all share the source coordinate.
