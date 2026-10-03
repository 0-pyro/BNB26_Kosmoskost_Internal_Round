/**
 * AudioWorklet Processor for Roundtable.
 *
 * Captures audio at the AudioContext's sample rate, downsamples to 16kHz,
 * accumulates 100ms frames (1600 samples at 16kHz), prepends a 16-byte
 * binary header, and posts the complete frame to the main thread.
 *
 * The main thread is responsible for sending via WebSocket.
 *
 * Message protocol (worklet -> main):
 *   { type: "audio-frame", frame: ArrayBuffer }
 *     where frame = 16-byte header + Float32 PCM payload
 *
 * Message protocol (main -> worklet):
 *   { type: "init", participantIdHash: number }
 *   { type: "set-seq", seqNum: number }       // for reconnect resync
 */

const MAGIC_0 = 0xAA;
const MAGIC_1 = 0xBB;
const TARGET_SAMPLE_RATE = 16000;
const FRAME_DURATION_MS = 100;
const SAMPLES_PER_FRAME = (TARGET_SAMPLE_RATE * FRAME_DURATION_MS) / 1000; // 1600
const HEADER_SIZE = 16;

class RoundtableProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this._buffer = new Float32Array(SAMPLES_PER_FRAME);
    this._bufferOffset = 0;
    this._seqNum = 0;
    this._participantIdHash = 0;
    this._ratio = sampleRate / TARGET_SAMPLE_RATE; // downsample ratio

    this.port.onmessage = (e) => {
      if (e.data.type === "init") {
        this._participantIdHash = e.data.participantIdHash;
      } else if (e.data.type === "set-seq") {
        this._seqNum = e.data.seqNum;
      }
    };
  }

  /**
   * Downsample from source rate to 16kHz using linear interpolation.
   */
  _downsample(input) {
    const ratio = this._ratio;
    const outputLen = Math.floor(input.length / ratio);
    const output = new Float32Array(outputLen);
    for (let i = 0; i < outputLen; i++) {
      const srcIdx = i * ratio;
      const low = Math.floor(srcIdx);
      const high = Math.min(low + 1, input.length - 1);
      const frac = srcIdx - low;
      output[i] = input[low] * (1 - frac) + input[high] * frac;
    }
    return output;
  }

  /**
   * Build 16-byte header (big-endian).
   *   [0:1]  0xAA 0xBB
   *   [2:3]  Participant ID Hash (UInt16)
   *   [4:7]  SeqNum (UInt32)
   *   [8:15] CaptureTS (BigUInt64, ms since epoch)
   */
  _buildHeader(captureTs) {
    const buf = new ArrayBuffer(HEADER_SIZE);
    const view = new DataView(buf);
    view.setUint8(0, MAGIC_0);
    view.setUint8(1, MAGIC_1);
    view.setUint16(2, this._participantIdHash, false); // big-endian
    view.setUint32(4, this._seqNum, false);
    view.setBigUint64(8, BigInt(captureTs), false);
    return buf;
  }

  process(inputs) {
    const input = inputs[0];
    if (!input || !input[0] || input[0].length === 0) {
      return true;
    }

    // Take mono channel (first channel)
    const raw = input[0];

    // Downsample if needed
    const samples = sampleRate === TARGET_SAMPLE_RATE ? raw : this._downsample(raw);

    let offset = 0;
    while (offset < samples.length) {
      const remaining = SAMPLES_PER_FRAME - this._bufferOffset;
      const toCopy = Math.min(remaining, samples.length - offset);

      this._buffer.set(samples.subarray(offset, offset + toCopy), this._bufferOffset);
      this._bufferOffset += toCopy;
      offset += toCopy;

      // Frame full — emit
      if (this._bufferOffset >= SAMPLES_PER_FRAME) {
        const captureTs = Date.now();
        const header = this._buildHeader(captureTs);

        // Build final frame: header + float32 PCM
        const pcmBytes = this._buffer.buffer.slice(0);
        const frame = new ArrayBuffer(HEADER_SIZE + pcmBytes.byteLength);
        const frameView = new Uint8Array(frame);
        frameView.set(new Uint8Array(header), 0);
        frameView.set(new Uint8Array(pcmBytes), HEADER_SIZE);

        this.port.postMessage({ type: "audio-frame", frame }, [frame]);

        // Reset buffer (need new one since we transferred ownership)
        this._buffer = new Float32Array(SAMPLES_PER_FRAME);
        this._bufferOffset = 0;
        this._seqNum++;
      }
    }

    return true; // keep processor alive
  }
}

registerProcessor("roundtable-processor", RoundtableProcessor);
