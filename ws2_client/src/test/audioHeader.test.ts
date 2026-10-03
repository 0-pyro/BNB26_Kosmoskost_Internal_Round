/**
 * Tests for binary audio frame header building.
 */

import { describe, it, expect } from "vitest";
import { buildAudioHeader, hashParticipantId, AUDIO_MAGIC_0, AUDIO_MAGIC_1, AUDIO_HEADER_SIZE } from "../types";

describe("buildAudioHeader", () => {
  it("creates a 16-byte buffer", () => {
    const buf = buildAudioHeader(0, 0, 0n);
    expect(buf.byteLength).toBe(AUDIO_HEADER_SIZE);
  });

  it("sets magic bytes correctly", () => {
    const buf = buildAudioHeader(0, 0, 0n);
    const view = new DataView(buf);
    expect(view.getUint8(0)).toBe(AUDIO_MAGIC_0);
    expect(view.getUint8(1)).toBe(AUDIO_MAGIC_1);
  });

  it("encodes participant hash as big-endian UInt16", () => {
    const buf = buildAudioHeader(0x1234, 0, 0n);
    const view = new DataView(buf);
    expect(view.getUint16(2, false)).toBe(0x1234);
  });

  it("encodes seq num as big-endian UInt32", () => {
    const buf = buildAudioHeader(0, 42, 0n);
    const view = new DataView(buf);
    expect(view.getUint32(4, false)).toBe(42);
  });

  it("encodes capture timestamp as big-endian UInt64", () => {
    const ts = BigInt(Date.now());
    const buf = buildAudioHeader(0, 0, ts);
    const view = new DataView(buf);
    expect(view.getBigUint64(8, false)).toBe(ts);
  });

  it("round-trips a complete header", () => {
    const pidHash = 0xABCD;
    const seq = 99;
    const ts = BigInt("1700000000000");

    const buf = buildAudioHeader(pidHash, seq, ts);
    const view = new DataView(buf);

    expect(view.getUint8(0)).toBe(0xAA);
    expect(view.getUint8(1)).toBe(0xBB);
    expect(view.getUint16(2, false)).toBe(pidHash);
    expect(view.getUint32(4, false)).toBe(seq);
    expect(view.getBigUint64(8, false)).toBe(ts);
  });
});

describe("hashParticipantId", () => {
  it("returns a 16-bit value", () => {
    const hash = hashParticipantId("p_abc123");
    expect(hash).toBeGreaterThanOrEqual(0);
    expect(hash).toBeLessThanOrEqual(0xFFFF);
  });

  it("returns same hash for same input", () => {
    const a = hashParticipantId("p_alice");
    const b = hashParticipantId("p_alice");
    expect(a).toBe(b);
  });

  it("returns different hashes for different inputs", () => {
    const a = hashParticipantId("p_alice");
    const b = hashParticipantId("p_bob");
    expect(a).not.toBe(b);
  });
});
