/**
 * Tests for useWebSocket hook — offline buffering and message handling.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useWebSocket } from "../hooks/useWebSocket";
import type { CaptionEvent, JoinAck } from "../types";

// ---------------------------------------------------------------------------
// Mock WebSocket
// ---------------------------------------------------------------------------

class MockWebSocket {
  static instances: MockWebSocket[] = [];
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSING = 2;
  static CLOSED = 3;
  url: string;
  binaryType = "blob";
  readyState = 0; // CONNECTING
  sentData: (string | ArrayBuffer)[] = [];

  onopen: (() => void) | null = null;
  onmessage: ((ev: { data: string | ArrayBuffer }) => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: ((err: unknown) => void) | null = null;

  constructor(url: string) {
    this.url = url;
    MockWebSocket.instances.push(this);
  }

  send(data: string | ArrayBuffer) {
    this.sentData.push(data);
  }

  close() {
    this.readyState = 3; // CLOSED
    if (this.onclose) this.onclose();
  }

  // Test helpers
  triggerOpen() {
    this.readyState = 1; // OPEN
    if (this.onopen) this.onopen();
  }

  triggerMessage(data: string | ArrayBuffer) {
    if (this.onmessage) this.onmessage({ data });
  }

  triggerClose() {
    this.readyState = 3;
    if (this.onclose) this.onclose();
  }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("useWebSocket", () => {
  beforeEach(() => {
    MockWebSocket.instances = [];
    vi.stubGlobal("WebSocket", MockWebSocket);
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.clearAllTimers();
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("initializes with disconnected state", () => {
    const onCaption = vi.fn();
    const onJoinAck = vi.fn();

    const { result } = renderHook(() =>
      useWebSocket({
        url: "ws://localhost:8000",
        sessionId: "ROOM1",
        participantName: "Alice",
        onCaption,
        onJoinAck,
      })
    );

    expect(result.current.status).toBe("disconnected");
    expect(result.current.participantId).toBeNull();
  });

  it("connects and sends JOIN message on open", () => {
    const onCaption = vi.fn();
    const onJoinAck = vi.fn();

    const { result } = renderHook(() =>
      useWebSocket({
        url: "ws://localhost:8000",
        sessionId: "ROOM1",
        participantName: "Alice",
        onCaption,
        onJoinAck,
      })
    );

    act(() => {
      result.current.connect();
    });

    expect(MockWebSocket.instances.length).toBe(1);
    const mockWs = MockWebSocket.instances[0];

    act(() => {
      mockWs.triggerOpen();
    });

    expect(result.current.status).toBe("connected");
    expect(mockWs.sentData.length).toBe(1);
    const joinMsg = JSON.parse(mockWs.sentData[0] as string);
    expect(joinMsg.type).toBe("JOIN");
    expect(joinMsg.session_id).toBe("ROOM1");
    expect(joinMsg.participant_name).toBe("Alice");
  });

  it("handles JOIN_ACK and transitions to joined state", () => {
    const onCaption = vi.fn();
    const onJoinAck = vi.fn();

    const { result } = renderHook(() =>
      useWebSocket({
        url: "ws://localhost:8000",
        sessionId: "ROOM1",
        participantName: "Alice",
        onCaption,
        onJoinAck,
      })
    );

    act(() => {
      result.current.connect();
    });

    const mockWs = MockWebSocket.instances[0];
    act(() => {
      mockWs.triggerOpen();
    });

    const ack: JoinAck = {
      type: "JOIN_ACK",
      participant_id: "p_12345",
      history: [],
    };

    act(() => {
      mockWs.triggerMessage(JSON.stringify(ack));
    });

    expect(result.current.status).toBe("joined");
    expect(result.current.participantId).toBe("p_12345");
    expect(onJoinAck).toHaveBeenCalledWith(ack);
  });

  it("routes CAPTION messages to onCaption callback", () => {
    const onCaption = vi.fn();
    const onJoinAck = vi.fn();

    const { result } = renderHook(() =>
      useWebSocket({
        url: "ws://localhost:8000",
        sessionId: "ROOM1",
        participantName: "Alice",
        onCaption,
        onJoinAck,
      })
    );

    act(() => {
      result.current.connect();
    });

    const mockWs = MockWebSocket.instances[0];
    act(() => {
      mockWs.triggerOpen();
    });

    const caption: CaptionEvent = {
      type: "CAPTION",
      segment_id: "seg_1",
      speaker_id: "p_12345",
      speaker_name: "Alice",
      start_ts: 100,
      end_ts: 200,
      text: "Hello world",
      is_final: false,
      revision: 1,
    };

    act(() => {
      mockWs.triggerMessage(JSON.stringify(caption));
    });

    expect(onCaption).toHaveBeenCalledWith(caption);
  });

  it("buffers audio frames when disconnected and flushes on reconnect", () => {
    const onCaption = vi.fn();
    const onJoinAck = vi.fn();

    const { result } = renderHook(() =>
      useWebSocket({
        url: "ws://localhost:8000",
        sessionId: "ROOM1",
        participantName: "Alice",
        onCaption,
        onJoinAck,
      })
    );

    // Send binary while disconnected
    const dummyFrame1 = new Uint8Array([1, 2, 3]).buffer;
    const dummyFrame2 = new Uint8Array([4, 5, 6]).buffer;

    act(() => {
      result.current.sendBinary(dummyFrame1);
      result.current.sendBinary(dummyFrame2);
    });

    // Now connect
    act(() => {
      result.current.connect();
    });

    const mockWs = MockWebSocket.instances[0];
    act(() => {
      mockWs.triggerOpen();
    });

    // Upon JOIN_ACK, buffered frames should be flushed
    const ack: JoinAck = {
      type: "JOIN_ACK",
      participant_id: "p_12345",
      history: [],
    };

    act(() => {
      mockWs.triggerMessage(JSON.stringify(ack));
    });

    // Sent data should contain: JOIN message, then dummyFrame1, dummyFrame2
    expect(mockWs.sentData.length).toBe(3);
    expect(mockWs.sentData[1]).toBe(dummyFrame1);
    expect(mockWs.sentData[2]).toBe(dummyFrame2);
  });
});
