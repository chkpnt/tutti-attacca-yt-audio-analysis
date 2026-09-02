// AudioWorkletProcessor for measure-click.html.
// Reports the absolute render frame of every detected click onset
// (first sample above threshold, 0.2 s merge gap) and a running peak
// so the page can distinguish "no click" from "silent tap".
class ClickDetector extends AudioWorkletProcessor {
  constructor() {
    super();
    this.peak = 0;
    this.last = -1e12;
    this.blocks = 0;
  }

  process(inputs) {
    const ch = inputs[0] && inputs[0][0];
    if (ch) {
      for (let i = 0; i < ch.length; i++) {
        const v = Math.abs(ch[i]);
        if (v > this.peak) this.peak = v;
        if (v > 0.05 && currentFrame + i - this.last > 0.2 * sampleRate) {
          this.last = currentFrame + i;
          this.port.postMessage({ click: this.last, peak: this.peak });
        }
      }
      if (++this.blocks % 100 === 0) {
        this.port.postMessage({ peak: this.peak });
      }
    }
    return true;
  }
}

registerProcessor('click-detector', ClickDetector);
