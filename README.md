# Audio timeline calibration fixtures

This directory contains reproducible source fixtures for validating the time-coordinate chain used by ProbeNavigator:

```text
known PCM timeline
  -> uploaded YouTube source video
  -> YouTube-generated AAC/M4A or Opus/WebM representation
  -> yt-dlp download
  -> Audacity timestamp authoring
  -> HTMLMediaElement.currentTime in Firefox and Safari
```

The purpose is to determine whether a timestamp read from the downloaded asset in Audacity targets the same audible instant when assigned to `HTMLMediaElement.currentTime` in the browser.

Three **master videos** are deliberately created from the same visual and PCM timeline but use different source-audio formats:

| Upload fixture | Container | Source audio codec | Why it exists |
|---|---|---|---|
| `calibration-wav.mov` | QuickTime/MOV | PCM WAV | Reference-quality upload; no lossy source-codec delay |
| `calibration-m4a.mp4` | MP4 | AAC-LC | Models a creator who uploads AAC/MP4 audio |
| `calibration-opus.webm` | WebM | Opus | Models a creator who uploads Opus/WebM audio |

YouTube creates its own delivery representations after upload. The input codecs above are therefore not expected to be served unchanged; the point is to test whether YouTube's generated AAC/M4A and Opus/WebM timelines depend on the creator's input format.

## Fixture design

All variants originate from `calibration.wav`, a 60.000-second, mono, 48 kHz PCM master. It contains five 50 ms, 1 kHz sine bursts at the following exact PCM positions:

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

The audio signal is intentionally simple. It has a sharp, high-contrast onset in Audacity's waveform/spectrogram, survives lossy re-encoding well, and avoids ambiguity from musical phrasing.

## Prerequisites

```bash
ffmpeg -version
ffprobe -version
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

## Generate the PCM master

Run all commands from this directory. The master contains audio only:

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

## Generate source audio variants

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

Expected codecs:

```text
calibration.wav   pcm_s24le, 48000 Hz, mono
calibration.m4a   aac,       typically 48000 Hz, mono
calibration.opus  opus,      48000 Hz, mono
```

Do not require byte-identical or exactly equal reported durations for the lossy outputs. Codec priming, final-frame padding, Ogg end trimming, and MP4 edit lists can affect raw decoder/container duration. The authoritative signal positions are the cue onsets after the relevant playback pipeline applies its presentation timeline.

## Generate the visual master

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

## Mux the three master videos

### WAV/PCM source: MOV

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

### AAC source: MP4

MP4 accepts the H.264 visual stream and AAC audio stream. Stream-copy both:

```bash
ffmpeg -y \
  -stream_loop -1 -i calibration-video.mp4 \
  -i calibration.m4a \
  -map 0:v:0 -map 1:a:0 \
  -c:v copy -c:a copy \
  -shortest \
  -movflags +faststart \
  calibration-m4a.mp4
```

### Opus source: WebM

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

## Validate before upload

Inspect all masters:

```bash
for f in calibration-wav.mov calibration-m4a.mp4 calibration-opus.webm; do
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
| `calibration-m4a.mp4` | H.264, 1280×720, 60 fps | AAC, 48 kHz mono |
| `calibration-opus.webm` | VP9, 1280×720, 60 fps | Opus, 48 kHz mono |

For an additional visual/audio sanity check, play each master locally. At every white flash, the 1 kHz beep must begin together. A phone slow-motion recording is sufficient to notice a muxing error, though not the primary timing measurement.

Generate checksums after final verification:

```bash
shasum -a 256 \
  calibration.wav calibration.m4a calibration.opus \
  calibration-video.mp4 \
  calibration-wav.mov calibration-m4a.mp4 calibration-opus.webm \
  > SHA256SUMS
```

Keep `SHA256SUMS` with the fixture sources so that a later test uses known assets.

## Upload and retrieve

Upload the three master videos to YouTube as **unlisted** videos. Record their IDs and the date/time at which HD/audio processing completed.

After processing completes, enumerate formats for each source upload:

```bash
yt-dlp -F "https://www.youtube.com/watch?v=<video-id>"
```

Download the actual representations relevant to the ProbeNavigator pipeline:

```bash
yt-dlp \
  -f 'bestaudio[ext=m4a][acodec^=mp4a]/bestaudio[ext=m4a]' \
  -o 'yt-<video-id>-aac.%(ext)s' \
  "https://www.youtube.com/watch?v=<video-id>"

yt-dlp \
  -f 'bestaudio[ext=webm][acodec=opus]' \
  -o 'yt-<video-id>-opus.%(ext)s' \
  "https://www.youtube.com/watch?v=<video-id>"
```

For each retrieved file, save `ffprobe` output with the test record:

```bash
for f in yt-*-aac.m4a yt-*-opus.webm; do
  [ -e "$f" ] || continue
  ffprobe -hide_banner "$f" 2>&1 | tee "$f.ffprobe.txt"
done
```

## Test procedure

### 1. Audacity authoring coordinate

For each downloaded M4A and Opus file:

1. Import the file into Audacity.
2. Open the waveform and spectrogram views.
3. Locate cue onsets A–E.
4. Record each displayed timestamp.
5. Compare the observed values to the WAV master positions.

This measures the timestamp coordinate an editor sees when authoring a `pieces/*.json5` file.

### 2. Browser presentation coordinate

Serve the downloaded files over HTTP, not `file:`:

```bash
python3 -m http.server 8000
```

Load each file in the real ProbeNavigator audio-mode player or a dedicated HTMLMediaElement test page. For each cue time, assign:

```js
audio.currentTime = 1.000;
audio.currentTime = 1.310;
audio.currentTime = 10.000;
audio.currentTime = 30.000;
audio.currentTime = 59.000;
```

Verify that playback begins at the matching beep/flash. Test at least:

- Firefox desktop;
- Safari on macOS;
- Safari on iOS.

Do not substitute Playwright's bundled WebKit build for Safari media testing; media codec and platform integration differ from shipping Safari.

### 3. Interpret results

| Observation | Meaning | Action |
|---|---|---|
| All cue offsets are constant between Audacity and the browser | A fixed authoring-coordinate difference | Document one global authoring offset; do not adjust marks one by one |
| Offset grows from cue A to E | Rate/timeline drift | Do not use that format/pipeline for timestamp-driven playback |
| M4A behaves correctly in every browser | MP4/AAC is suitable as canonical audio | Ship AAC-only |
| Ogg/Opus behaves correctly in Firefox but Safari reports a wrong duration or wrong late seeks | WebKit Ogg/Opus timeline defect | Keep Ogg/Opus disabled in production |
| M4A and Opus results depend on whether the upload source was WAV, AAC, or Opus | YouTube ingestion affects rendition alignment | Preserve all three upload fixtures and author against the exact canonical downloaded rendition |

## ProbeNavigator policy

This fixture does not replace per-piece spot checks. It establishes the coordinate-system contract for a particular toolchain and browser version.

For the current Safari Ogg/Opus defect, the decisive requirement is not that Safari decodes sound: Safari must report a correct `HTMLMediaElement.duration` and seek each cue to the expected audible instant. Ogg/Opus remains an experimental/future profile until that is true.

MP4/AAC remains the canonical production format unless this fixture demonstrates a browser-visible timing mismatch that cannot be represented as a stable global authoring offset.
