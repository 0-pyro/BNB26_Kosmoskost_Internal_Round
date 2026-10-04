import { useCallback, useState } from "react";
import { CaptionDisplay } from "./components/CaptionDisplay";
import { JoinScreen } from "./components/JoinScreen";
import { StatusBar } from "./components/StatusBar";
import { useAudioCapture } from "./hooks/useAudioCapture";
import { useCaptions } from "./hooks/useCaptions";
import { useWakeLock } from "./hooks/useWakeLock";
import { useWebSocket } from "./hooks/useWebSocket";
import type { CaptionEvent, JoinAck } from "./types";
import "./App.css";

// Dynamic WebSocket URL: uses wss: over HTTPS tunnels and ws: over local/LAN
function getDefaultWsUrl(): string {
  if (typeof window === "undefined") return "ws://localhost:8000/ws";
  const isHttps = window.location.protocol === "https:";
  const proto = isHttps ? "wss:" : "ws:";
  const port = isHttps ? "" : (window.location.port === "8000" ? ":8000" : ":8000");
  return `${proto}//${window.location.hostname}${port}/ws`;
}

const DEFAULT_WS_URL = getDefaultWsUrl();

type ViewMode = "grouped" | "timeline";

function App() {
  const [sessionConfig, setSessionConfig] = useState<{
    url: string;
    sessionId: string;
    participantName: string;
  } | null>(null);

  const [viewMode, setViewMode] = useState<ViewMode>("timeline");

  const { speakerGroups, timeline, handleCaption, loadHistory, clearCaptions } =
    useCaptions();

  const wakeLock = useWakeLock();

  const [latencyHistory, setLatencyHistory] = useState<number[]>([]);

  const onCaption = useCallback(
    (event: CaptionEvent) => {
      handleCaption(event);
      if (event.end_ts > 0) {
        const now = Date.now();
        const rawDelta = now - event.end_ts;
        const lat = rawDelta > 0 && rawDelta < 10000 ? rawDelta : (event.end_ts - event.start_ts);
        const validLat = Math.max(50, Math.min(lat, 2500));
        setLatencyHistory((prev) => [...prev.slice(-19), validLat]);
      }
    },
    [handleCaption],
  );

  const onJoinAck = useCallback(
    (ack: JoinAck) => {
      if (ack.history.length > 0) {
        loadHistory(ack.history);
      }
      // Acquire wake lock when joining
      wakeLock.request();
    },
    [loadHistory, wakeLock],
  );

  const ws = useWebSocket({
    url: sessionConfig?.url ?? DEFAULT_WS_URL,
    sessionId: sessionConfig?.sessionId ?? "",
    participantName: sessionConfig?.participantName ?? "",
    onCaption,
    onJoinAck,
  });

  const audio = useAudioCapture({
    participantId: ws.participantId,
    onFrame: ws.sendBinary,
  });

  const handleJoin = useCallback(
    async (sessionId: string, name: string, serverUrl?: string) => {
      const targetUrl = serverUrl || DEFAULT_WS_URL;
      setSessionConfig({
        url: targetUrl,
        sessionId,
        participantName: name,
      });
      // Start audio capture first (needs user gesture for iOS Safari)
      await audio.startCapture();
      // Then connect WebSocket with credentials directly
      ws.connect({
        url: targetUrl,
        sessionId,
        participantName: name,
      });
    },
    [audio, ws],
  );

  const handleDisconnect = useCallback(() => {
    audio.stopCapture();
    ws.disconnect();
    wakeLock.release();
    clearCaptions();
    setLatencyHistory([]);
    setSessionConfig(null);
  }, [audio, ws, wakeLock, clearCaptions]);

  const latestLatency = latencyHistory.length > 0 ? latencyHistory[latencyHistory.length - 1] : undefined;
  const p95Latency = latencyHistory.length > 0
    ? [...latencyHistory].sort((a, b) => a - b)[Math.floor(latencyHistory.length * 0.95)]
    : undefined;

  // Show join screen if no session config
  if (!sessionConfig) {
    return (
      <JoinScreen
        onJoin={handleJoin}
        isConnecting={ws.status === "connecting"}
      />
    );
  }

  // Session view
  return (
    <div className="app-container" data-testid="app-container">
      <StatusBar
        connectionStatus={ws.status}
        captureStatus={audio.captureStatus}
        isWakeLocked={wakeLock.isLocked}
        participantId={ws.participantId}
        roomName={sessionConfig.sessionId}
        captionCount={timeline.length}
        latencyMs={latestLatency}
        p95LatencyMs={p95Latency}
        onDisconnect={handleDisconnect}
        onStopCapture={audio.stopCapture}
      />

      <div className="view-toggle">
        <button
          className={`toggle-btn ${viewMode === "timeline" ? "active" : ""}`}
          onClick={() => setViewMode("timeline")}
          data-testid="view-timeline"
        >
          Timeline
        </button>
        <button
          className={`toggle-btn ${viewMode === "grouped" ? "active" : ""}`}
          onClick={() => setViewMode("grouped")}
          data-testid="view-grouped"
        >
          By Speaker
        </button>
      </div>

      <CaptionDisplay
        speakerGroups={speakerGroups}
        timeline={timeline}
        viewMode={viewMode}
      />
    </div>
  );
}

export default App;
