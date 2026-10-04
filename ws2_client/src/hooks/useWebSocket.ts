import { useCallback, useEffect, useRef, useState } from "react";
import type { CaptionEvent, JoinAck, JoinRequest, ServerMessage } from "../types";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type ConnectionStatus = "disconnected" | "connecting" | "connected" | "joined";

export interface UseWebSocketOptions {
  url: string;
  sessionId: string;
  participantName: string;
  onCaption: (event: CaptionEvent) => void;
  onJoinAck: (ack: JoinAck) => void;
  /** Max seconds to buffer audio frames while disconnected. Default 60. */
  maxBufferSecs?: number;
}

export interface UseWebSocketReturn {
  status: ConnectionStatus;
  participantId: string | null;
  sendBinary: (data: ArrayBuffer) => void;
  connect: (override?: { url?: string; sessionId?: string; participantName?: string }) => void;
  disconnect: () => void;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const INITIAL_RECONNECT_MS = 1000;
const MAX_RECONNECT_MS = 16000;
const DEFAULT_MAX_BUFFER_SECS = 60;

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useWebSocket(options: UseWebSocketOptions): UseWebSocketReturn {
  const {
    url,
    sessionId,
    participantName,
    onCaption,
    onJoinAck,
    maxBufferSecs = DEFAULT_MAX_BUFFER_SECS,
  } = options;

  const [status, setStatus] = useState<ConnectionStatus>("disconnected");
  const [participantId, setParticipantId] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectDelayRef = useRef(INITIAL_RECONNECT_MS);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const offlineBufferRef = useRef<ArrayBuffer[]>([]);
  const bufferStartRef = useRef<number | null>(null);
  const intentionalCloseRef = useRef(false);

  // Keep callbacks fresh without re-triggering effects
  const onCaptionRef = useRef(onCaption);
  onCaptionRef.current = onCaption;
  const onJoinAckRef = useRef(onJoinAck);
  onJoinAckRef.current = onJoinAck;

  const configRef = useRef({ url, sessionId, participantName });
  configRef.current = {
    url: url || configRef.current.url,
    sessionId: sessionId || configRef.current.sessionId,
    participantName: participantName || configRef.current.participantName,
  };

  const clearReconnectTimer = useCallback(() => {
    if (reconnectTimerRef.current !== null) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
  }, []);

  // Flush buffered audio frames on reconnect
  const flushBuffer = useCallback((ws: WebSocket) => {
    const frames = offlineBufferRef.current;
    if (frames.length === 0) return;
    console.log(`[ws] Flushing ${frames.length} buffered audio frames`);
    for (const frame of frames) {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(frame);
      }
    }
    offlineBufferRef.current = [];
    bufferStartRef.current = null;
  }, []);

  const doConnect = useCallback((override?: { url?: string; sessionId?: string; participantName?: string }) => {
    if (override) {
      if (override.url) configRef.current.url = override.url;
      if (override.sessionId) configRef.current.sessionId = override.sessionId;
      if (override.participantName) configRef.current.participantName = override.participantName;
    }

    if (wsRef.current && wsRef.current.readyState <= WebSocket.OPEN) {
      return; // already connected or connecting
    }

    const targetUrl = configRef.current.url || url;
    const targetSessionId = configRef.current.sessionId || sessionId;
    const targetParticipantName = configRef.current.participantName || participantName;

    intentionalCloseRef.current = false;
    setStatus("connecting");
    const ws = new WebSocket(targetUrl);
    ws.binaryType = "arraybuffer";
    wsRef.current = ws;

    ws.onopen = () => {
      console.log("[ws] Connected to", targetUrl, "room:", targetSessionId, "user:", targetParticipantName);
      setStatus("connected");
      reconnectDelayRef.current = INITIAL_RECONNECT_MS;

      let savedPid: string | undefined = undefined;
      try {
        const stored = sessionStorage.getItem(`roundtable_pid_${targetSessionId}_${targetParticipantName}`);
        if (stored) savedPid = stored;
      } catch {
        // ignore
      }

      // Send JOIN
      const joinMsg: JoinRequest = {
        type: "JOIN",
        session_id: targetSessionId,
        participant_name: targetParticipantName,
        ...(savedPid ? { participant_id: savedPid } : {}),
      };
      ws.send(JSON.stringify(joinMsg));
    };

    ws.onmessage = (event: MessageEvent) => {
      if (typeof event.data === "string") {
        try {
          const msg: ServerMessage = JSON.parse(event.data);
          switch (msg.type) {
            case "JOIN_ACK": {
              setParticipantId(msg.participant_id);
              try {
                sessionStorage.setItem(`roundtable_pid_${targetSessionId}_${targetParticipantName}`, msg.participant_id);
              } catch {
                // ignore
              }
              setStatus("joined");
              onJoinAckRef.current(msg);
              // Flush any buffered frames
              flushBuffer(ws);
              break;
            }
            case "CAPTION":
              onCaptionRef.current(msg);
              break;
            case "SYNC_ACK":
              // Time sync — not required for Pass 1
              break;
            default:
              console.warn("[ws] Unknown message type", msg);
          }
        } catch (err) {
          console.error("[ws] Failed to parse message", err);
        }
      }
    };

    ws.onclose = () => {
      console.log("[ws] Disconnected");
      wsRef.current = null;
      setStatus("disconnected");

      if (!intentionalCloseRef.current) {
        // Schedule reconnect with exponential backoff
        const delay = reconnectDelayRef.current;
        console.log(`[ws] Reconnecting in ${delay}ms...`);
        reconnectTimerRef.current = setTimeout(() => {
          reconnectTimerRef.current = null;
          doConnect();
        }, delay);
        reconnectDelayRef.current = Math.min(delay * 2, MAX_RECONNECT_MS);
      }
    };

    ws.onerror = (err) => {
      console.error("[ws] Error", err);
      // onclose will fire after this
    };
  }, [url, sessionId, participantName, flushBuffer]);

  const disconnect = useCallback(() => {
    intentionalCloseRef.current = true;
    clearReconnectTimer();
    try {
      const targetSessionId = configRef.current.sessionId || sessionId;
      const targetParticipantName = configRef.current.participantName || participantName;
      sessionStorage.removeItem(`roundtable_pid_${targetSessionId}_${targetParticipantName}`);
    } catch {
      // ignore
    }
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    setStatus("disconnected");
    setParticipantId(null);
    offlineBufferRef.current = [];
    bufferStartRef.current = null;
  }, [clearReconnectTimer, sessionId, participantName]);

  // Send binary data, buffering if offline (up to maxBufferSecs)
  const sendBinary = useCallback(
    (data: ArrayBuffer) => {
      const ws = wsRef.current;
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(data);
        return;
      }

      // Buffer offline frames
      const now = Date.now();
      if (bufferStartRef.current === null) {
        bufferStartRef.current = now;
      }

      const elapsed = (now - bufferStartRef.current) / 1000;
      if (elapsed <= maxBufferSecs) {
        offlineBufferRef.current.push(data);
      }
      // else: drop frame — buffer window exceeded
    },
    [maxBufferSecs],
  );

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      intentionalCloseRef.current = true;
      clearReconnectTimer();
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [clearReconnectTimer]);

  return {
    status,
    participantId,
    sendBinary,
    connect: doConnect,
    disconnect,
  };
}
