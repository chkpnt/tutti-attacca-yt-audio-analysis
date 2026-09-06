// AudioWorkletProcessor used by measure-click.html.
//
// The processor observes the samples emitted by an HTMLMediaElement through
// AudioContext.createMediaElementSource(). It reports the absolute AudioContext
// render frame for the first sample of each 1 kHz calibration burst. The page
// maps that frame to HTMLMediaElement.currentTime using clock pairs collected
// during steady playback.
//
// `currentFrame` is the first frame of the current render quantum. Unlike a
// ScriptProcessor callback, this code runs on the audio rendering thread, so
// `currentFrame + i` is the precise sample position in the AudioContext clock.
// That avoids capture-start latency and main-thread callback scheduling bias.
//
// One processor instance is shared across all measured files; the page sends
// { type: 'reset' } before each file to clear the click/peak state.
//
// Fixture contract:
// - bursts are 50 ms, 1 kHz tones;
// - burst starts are at 1.000, 1.310, 10.000, 30.000, and 59.000 seconds;
// - 0.05 is deliberately far below the 0.8 source amplitude but above codec
//   noise / numerical residue;
// - 0.2 s is safely below the 0.310 s A->B gap but prevents multiple reports
//   while one 50 ms tone crosses the threshold repeatedly.
class ClickDetector extends AudioWorkletProcessor {
  constructor() {
    super();
    this.lastClickFrame = -Infinity;
    this.peak = 0;
    this.blocks = 0;

    // A positive ready message distinguishes a module/path/CSP failure from a
    // live-but-silent media-element source.
    this.port.postMessage({ type: 'ready', sampleRate });

    this.port.onmessage = (event) => {
      if (event.data && event.data.type === 'reset') {
        this.lastClickFrame = -Infinity;
        this.peak = 0;
      }
    };
  }

  process(inputs) {
    const input = inputs[0];
    const channel = input && input[0];

    // A source can briefly have no channel while it is loading or seeking. Do
    // not stop the processor: returning true keeps it alive for later blocks.
    if (!channel) return true;

    for (let i = 0; i < channel.length; i++) {
      const value = Math.abs(channel[i]);
      if (value > this.peak) this.peak = value;

      const frame = currentFrame + i;
      if (value > 0.05 && frame - this.lastClickFrame > 0.2 * sampleRate) {
        this.lastClickFrame = frame;

        // `frame` is in the AudioContext timeline, not media-file time. The
        // main page combines it with getOutputTimestamp/currentTime pairs.
        this.port.postMessage({ type: 'click', frame, peak: this.peak });
      }
    }

    // Status makes the failure modes observable without moving per-sample data
    // to the main thread: peak=0 means silence; peak>0 + no click hints at an
    // unsuitable threshold or unexpected calibration input.
    if (++this.blocks % 100 === 0) {
      this.port.postMessage({ type: 'status', frame: currentFrame, peak: this.peak });
    }

    return true;
  }
}

registerProcessor('click-detector', ClickDetector);
