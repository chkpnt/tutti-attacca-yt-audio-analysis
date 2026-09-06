# Audio timeline calibration fixtures

This directory contains reproducible source fixtures for validating the time-coordinate chain used by ProbeNavigator:

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
│   ├── calibration.opus               # local Opus encode
│   ├── calibration-video.mp4          # visual master (white-flash track)
│   ├── calibration-wav.mov            # upload master, PCM audio
│   ├── calibration-aac.mp4            # upload master, AAC audio
│   └── calibration-opus.webm          # upload master, Opus audio
├── yt-downloads/                       # YouTube delivery assets + browser harness
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

Verify them:

```bash
for f in calibration.wav calibration.m4a calibration.opus; do
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
  calibration.wav calibration.m4a calibration.opus \
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

The corrected M4A reports `duration: 60.034 s` (60.070 s minus the 36.3 ms priming moved out of the presentation timeline). Its major_brand changes from `isom` to `M4A` — an artifact of FFmpeg's default branding for the `.m4a` extension, cosmetically avoidable with `-brand isom`.

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
| `yt_calibration-wav-corrected.m4a` | expected: `segment_duration=2647488` (60.0337 s at 44.1 kHz = 2649088 − 1600), `media_time=1600`, `rate=1` | Priming trimmed → source-aligned. **Pending:** dump confirmation on the real file (mechanism verified on a simulated fixture, see below) |

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

Mechanism: `-itsoffset` shifts the input timestamps; the first packet lands at a negative PTS (−1600 samples at 44.1 kHz), and the MP4 muxer — which cannot store negative media times — re-bases the media timeline and records the shift as an edit list (`elst` with `media_time=1600`). The AAC bitstream is copied unchanged (`-c:a copy`); only container metadata is added. The result carries exactly the same edit-list structure that makes the locally encoded `master/calibration.m4a` source-aligned everywhere — just with YouTube's 1600-sample priming instead of FFmpeg's 1024. The mechanism was validated on a simulated fixture (undeclared priming → muxer writes the trimming edit list; decode-aligned; bitstream MD5-identical); the edit-list values stated above for the real corrected file are the expected ones and should be confirmed once with `dump-elst.py`.

The offset constant is 1600 samples at 44.1 kHz = 36.281 ms (`-itsoffset -0.0362812`); cross-correlation against the Opus rendition (`scripts/compare-drift.py`) measured 36.292 ± 0.02 ms. It is a global property of YouTube's AAC rendition: the same +36.3 ms was measured on an unrelated real piece (video `xX1Y0cxstBw`, outside this fixture set). It must **not** be applied to locally encoded files or to a last-resort local transcode of a YouTube track, both of which are already source-aligned.

Verification of the corrected fixture (2026-09-03):

- `extract-clicks.py`: onsets 1.0000 / 1.3100 / 10.0000 / 30.0000 / 59.0000 s — all five cues at **+0.0 ms**, spread 0.0 ms. FFmpeg applies the new edit list on decode.
- Audacity: imported side by side with `master/calibration.m4a`, all peaks align exactly; the corrected file displays 34 ms longer (60.034 vs 60.000 s) because YouTube's larger end padding survives in the raw span — cosmetic.
- Browser: see "Browser results → Corrected M4A". A Safari pass of the corrected fixture is still pending; expect aligned presentation and an element duration of ~59.986 s (Safari's established 48 ms end-trim is cosmetic).

Guard for the pipeline: after correcting a fresh download, `extract-clicks.py` must read 0.0 ms. If a future YouTube download measures an offset different from +36.3 ms, YouTube changed its encoding pipeline and the constant must be re-derived.

## Browser measurement harness

The browser harness lives in `yt-downloads/` next to the delivery assets and contains two files that must be served together over HTTP:

```text
yt-downloads/measure-click.html
yt-downloads/click-worklet.js
```

`measure-click.html` is preconfigured to test the YouTube delivery files (and optionally the corrected M4A) sequentially. It creates a fresh `AudioContext`, `<audio>` element, `MediaElementAudioSourceNode`, `AudioWorkletNode`, and output gain for each input, then releases all resources before moving to the next file.

`click-worklet.js` detects the first sample above the calibration threshold in the AudioWorklet rendering thread. It reports the absolute `currentFrame` for each click, avoiding the capture-start / ScriptProcessor scheduling errors encountered by earlier test pages.

The harness maps a worklet frame to the media-element timeline by collecting steady-state pairs of:

```js
[ctx.getOutputTimestamp().contextTime, audio.currentTime]
```

It computes the median of `audio.currentTime - contextTime` and applies that constant to the click's AudioContext render time. It therefore aims to answer the product question directly:

> At which `HTMLMediaElement.currentTime` does the browser present each calibration click?

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

The worklet output is connected to an intentionally tiny non-zero gain (`0.00001`). A literal zero-gain branch can be optimized away; the chosen value keeps the graph live while remaining effectively inaudible. Gain staging differs between engines: Safari may make the calibration tones audible where Firefox and Chromium stay silent. Audibility does not affect the measurement.

### Secure contexts and iOS

AudioWorklet requires a secure context. `http://localhost` qualifies; a plain HTTP LAN URL (e.g. `http://192.168.x.x:8000` on a phone) does **not** and fails with:

```text
ERROR: undefined is not an object (evaluating 'ctx.audioWorklet.addModule')
```

For iOS testing, serve the harness over HTTPS — a locally trusted certificate or a tunnel such as `cloudflared tunnel --url http://localhost:8000` — then open `https://<host>/yt-downloads/measure-click.html`, and feature-detect `audioWorklet` before invoking it. The 2026-09-03 iOS run used HTTPS and worked.

### Measurement interpretation

Absolute click values contain a stable per-browser clock-mapping bias; the meaningful result is the difference between same-browser local controls (`calibration.wav`, `calibration.m4a`) and the YouTube M4A files.

| Observation | Meaning |
|---|---|
| Local `calibration.wav` and `calibration.m4a` agree | Local AAC edit-list/presentation accounting is aligned in that browser |
| YouTube M4A later than local controls by about +36 ms | Browser exposes the YouTube M4A raw AAC coordinate |
| YouTube M4A agrees with local controls | Browser trims/maps the YouTube AAC origin to source presentation time |
| Corrected M4A agrees with local controls | The sync-time edit-list correction works in that browser |
| Two click results are 0.310000 s apart | No rate drift over the measured segment |
| `peak=0.00000` while playback is audible | WebKit silent-tap limitation: the media element's audio does not reach `createMediaElementSource` for that codec; a harness limitation, not a playback defect |

## Browser results

### Firefox

Firefox 48 kHz AudioContext measurements:

| File group | Element duration | Click A | Click B | Difference to local WAV |
|---|---:|---:|---:|---:|
| `calibration.wav` | 60.000 s | 0.9953 s | 1.3053 s | baseline |
| `calibration.m4a` | 60.000 s | 0.9953 s | 1.3053 s | 0.0 ms |
| each `yt_calibration-*.m4a` | 60.070 s | 1.0323 s | 1.3423 s | **+37.0 ms** |
| `yt_calibration-*.webm` | 60.021/60.041 s | 1.0028 s | 1.3128 s | control; source-aligned |

Firefox exposes the YouTube M4A raw coordinate: a source-time 1.000 s click presents at approximately `currentTime = 1.0323`, i.e. +37.0 ms relative to the local WAV/M4A baseline. Local FFmpeg-encoded AAC is fully aligned with WAV. A→B spacing is exactly 0.310000 s everywhere.

### Chromium

Chromium 48 kHz AudioContext measurements:

| File group | Element duration | Click A | Click B | Difference to local WAV |
|---|---:|---:|---:|---:|
| `calibration.wav` | 60.000 s | 1.0273 s | 1.3373 s | baseline |
| `calibration.m4a` | 60.000 s | 1.0272 s | 1.3372 s | −0.1 ms |
| each `yt_calibration-*.m4a` | 60.070 s | 1.0649–1.0650 s | 1.3749–1.3750 s | **+37.6–37.8 ms** |
| `yt_calibration-*.webm` | 60.021/60.041 s | 1.0270–1.0272 s | 1.3370–1.3372 s | control; source-aligned |

Chromium matches Firefox: local AAC is aligned with WAV, every YouTube M4A is approximately +37.7 ms later than the baseline, and the A→B spacing is exactly 0.310000 s.

### Safari macOS

M4A measurements across two sessions:

| File | Run 1 click A | Run 2 click A | Element duration |
|---|---:|---:|---:|
| `calibration.wav` | 0.9017 s | 0.9099 s | 60.000 s |
| `calibration.m4a` | — | 0.9050 s | 59.977 s |
| `yt_calibration-wav.m4a` | 0.9378 s | 0.9449 s | 60.022 s |
| `yt_calibration-aac.m4a` | 0.9315 s | 0.9399 s | 60.022 s |
| `yt_calibration-opus.m4a` | 0.9392 s | 0.9340 s | 60.022 s |

Safari's absolute mapping carries a −90…−100 ms harness bias that varies ±5–8 ms between runs (the WAV control itself moved 8.2 ms). Relative to the same-run WAV control, the YouTube M4A clicks sit +24…+37 ms later; relative to the local M4A control, +29…+40 ms. Both ranges are consistent with the +36.3 ms raw-decode offset.

Conclusions:

- **Safari does not remove YouTube's leading AAC priming from the `currentTime` origin.** Its reduced M4A element durations (60.022 s vs. 60.070 s for YouTube M4A; 59.977 s vs. 60.000 s for the local file) are end-side accounting — trailing padding / final-frame handling — not an origin shift. Proof: the local M4A aligns with the WAV control despite its trimmed duration.
- The three YouTube upload arms are indistinguishable; their ordering flips between runs within the harness noise, matching the offline analysis.

WebM/Opus measurements:

| File | Element duration | Worklet result |
|---|---:|---|
| `yt_calibration-wav.webm` | 60.014 s | peak 0.00000, no clicks detected |
| `yt_calibration-aac.webm` | 60.021 s | peak 0.00000, no clicks detected |
| `yt_calibration-opus.webm` | 60.041 s | peak 0.00000, no clicks detected |

The clicks were **audible** through the speakers while the Web Audio tap reported digital silence. This is the WebKit silent-tap limitation: for WebM/Opus the media element's output does not reach `createMediaElementSource`, even though playback itself works. It does not affect ProbeNavigator, which plays the element directly and draws the waveform from precomputed peaks rather than tapping the element through Web Audio.

The WebM element durations are correct (matching ffprobe within a few ms). This confirms that WebKit bug 293310 is specific to the **Ogg** container: the same Opus stream in WebM presents a correct duration in Safari. Seek accuracy for WebM/Opus in Safari could not be measured with this harness because of the silent tap.

### Safari iOS

Measured 2026-09-03 over HTTPS (see "Secure contexts and iOS"). Single session:

| File | Click A | Element duration | Difference to WAV |
|---|---:|---:|---:|
| `calibration.wav` | 0.8985 s | 60.000 s | baseline |
| `calibration.m4a` | 0.8985 s | 59.977 s | **+0.0 ms** |
| `yt_calibration-wav.m4a` | 0.9282 s | 60.022 s | **+29.7 ms** |
| `yt_calibration-aac.m4a` | 0.9282 s | 60.022 s | **+29.7 ms** |
| `yt_calibration-opus.m4a` | 0.9284 s | 60.022 s | **+29.9 ms** |

iOS matches macOS Safari exactly in structure: same ~−100 ms harness bias, local M4A perfectly aligned with WAV, YouTube M4A offset by ~+30 ms — consistent with the offline +36.3 ms value within Safari's observed ±5–8 ms run-to-run noise. The three upload arms agree within 0.2 ms. A→B spacing is exactly 0.310000 s.

### Corrected M4A

Desktop run 2026-09-03, 48 kHz AudioContext (engine name TODO — Firefox/Chromium-class; element durations rule out Safari):

| File | Element duration | Click A | Click B | Difference to local WAV |
|---|---:|---:|---:|---:|
| `calibration.wav` | 60.000 s | 0.9920 s | 1.3020 s | baseline |
| `calibration.m4a` | 60.000 s | 0.9920 s | 1.3020 s | 0.0 ms |
| `yt_calibration-wav.m4a` | 60.070 s | 1.0290 s | 1.3390 s | **+37.0 ms** |
| `yt_calibration-wav-corrected.m4a` | 60.034 s | 0.9927 s | 1.3027 s | **+0.7 ms** |

The WAV control lands at 0.9920 instead of 1.0000 — this run's clock-mapping bias is −8 ms, so only within-run differences are meaningful. Against that baseline, the uncorrected YouTube M4A is late by exactly the priming (+37.0 ms), while the corrected file agrees with both local controls within 0.7 ms. The 60.034 s element duration confirms that the browser honors the new edit list's presentation span.

## Conclusions

### YouTube delivery timing

- YouTube's output timing is independent of whether the source upload used PCM, AAC, or Opus.
- YouTube WebM/Opus decodes at the source cue positions in FFmpeg analysis.
- YouTube M4A/AAC decodes with a fixed +36.3 ms content offset in FFmpeg/Audacity-like raw decode analysis.
- The AAC offset is constant from 1 s to 59 s; it is priming/origin accounting, not stretching or rate drift.
- The offset is a property of **YouTube's** AAC rendition, not of AAC/MP4 in general: the locally encoded `master/calibration.m4a` (FFmpeg edit list, `media_time=1024`) presents source-aligned in every engine tested.
- The YouTube M4A declares no trim signaling at all (identity edit list, no `iTunSMPB`), so the raw coordinate is the only coordinate any consumer can present — the behaviour cannot silently change due to metadata-interpretation differences.
- The missing trim can be restored losslessly at sync time: a stream copy with `-itsoffset -0.0362812` makes the muxer write an edit list with `media_time=1600`, after which the M4A presents source-aligned in FFmpeg decode, Audacity, and the browser element.

### Browser timing (verified 2026-09-02/03)

| Engine / platform | Local M4A vs WAV | YouTube M4A vs control | Corrected M4A vs control |
|---|---:|---:|---:|
| FFmpeg/Audacity raw decode | 0.0 ms | +36.3 ms (exact) | 0.0 ms (exact) |
| Firefox desktop | 0.0 ms | +37.0 ms | pending |
| Chromium desktop | −0.1 ms | +37.7 ms | pending |
| Safari macOS (2 runs) | −4.9 ms | +24…+40 ms | pending |
| Safari iOS | +0.0 ms | +29.7 ms | pending |
| Desktop run 2026-09-03 (engine TODO) | 0.0 ms | +37.0 ms | **+0.7 ms** |

- All four engine/platform combinations present the uncorrected YouTube M4A in its raw-decoded (Audacity) coordinate, within the harness's noise band around the offline +36.3 ms value.
- All four present a locally encoded, properly edit-listed AAC file source-aligned — and the corrected YouTube M4A carries exactly that same edit-list structure, so it inherits the aligned behavior (verified in one desktop engine; the remaining passes are expected to match and are listed as pending).
- No engine rescales or drifts M4A: cue spacing is exactly preserved everywhere.
- Safari's media-element output for WebM/Opus does not reach the Web Audio tap (silent tap), while duration metadata is correct. Ogg/Opus remains broken in Safari per WebKit bug 293310 (scaled duration/timeline), reproduced independently with a real recording; the defect is specific to the Ogg container.

### Timestamp authoring policy (final)

1. **Canonical coordinate: the source PCM timeline.** It is presented identically by the uploaded video (and hence the YouTube IFrame player, which keeps its Opus audio rendition in A/V sync with the video track), by YouTube's Opus/WebM download, by locally encoded files, and by the corrected YouTube M4A. Marks authored against any of these artifacts are mutually valid without conversion. Marks read from an *uncorrected* YouTube M4A sit +36.3 ms late relative to source and would need `t_src = t_m4a − 0.0363`; the pipeline avoids that case by correcting the artifact instead.
2. **YouTube pieces: correct the artifact once at sync time.** Download the M4A (itag 140), then `ffmpeg -itsoffset -0.0362812 -i <download>.m4a -c:a copy audio/<key>.m4a`; verify with `scripts/dump-elst.py` (`media_time=1600`) and `scripts/extract-clicks.py` (0.0 ms). Author timestamps against the corrected M4A or the WebM download in Audacity — both expose the source coordinate. Legacy marks authored against Opus artifacts are already source-aligned and remain valid unchanged.
3. Record which artifact and coordinate system a piece's marks belong to in the piece JSON5 (see the `authoring` provenance object in the piece format spec), so future format changes remain documented constant shifts rather than archaeology.
4. Ogg/Opus remains disabled for production on WebKit (bug 293310). The experimental Opus pipeline is preserved behind the `AUDIO_FORMAT` build/sync profile and may be re-evaluated when Safari reports a correct `HTMLMediaElement.duration` and correct seeks for the Ogg/Opus calibration fixture.
5. The +36.3 ms offset and its correction are specific to YouTube's AAC rendition. Own recordings encoded locally with FFmpeg (`media-in` pipeline) are source-aligned in all engines and need no correction.
6. The same piece JSON drives both player modes, and both are now source-aligned: the YouTube IFrame player via its Opus rendition and A/V sync, the audio mode via the corrected M4A. Neither mode carries a systematic residual, and the player needs no runtime offset or browser detection. (Musically the residual question is moot anyway: 36 ms is below one frame at the typical 25 fps of score videos — but exact beats negligible.)

MP4/AAC is the canonical production format. Its only timing deviation — the constant, measurable, well-understood +36.3 ms YouTube rendition offset — is corrected once at sync time by a lossless edit-list remux, so JSON timestamps, precomputed peaks, Audacity authoring, and both player modes all share the source coordinate.
