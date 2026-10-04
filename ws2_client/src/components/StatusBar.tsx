import type { ConnectionStatus } from "../hooks/useWebSocket";
import type { AudioCaptureStatus } from "../hooks/useAudioCapture";
import "./StatusBar.css";

interface StatusBarProps {
  connectionStatus: ConnectionStatus;
  captureStatus: AudioCaptureStatus;
  isWakeLocked: boolean;
  participantId: string | null;
  roomName?: string;
  captionCount?: number;
  latencyMs?: number;
  p95LatencyMs?: number;
  onDisconnect: () => void;
  onStopCapture: () => void;
  onOpenDrawer?: () => void;
  onSaveSession?: () => void;
}

function statusLabel(s: ConnectionStatus): string {
  switch (s) {
    case "disconnected": return "Disconnected";
    case "connecting": return "Connecting";
    case "connected": return "Connected";
    case "joined": return "Live";
  }
}

function statusColor(s: ConnectionStatus): string {
  switch (s) {
    case "disconnected": return "#ef4444";
    case "connecting": return "#f59e0b";
    case "connected": return "#3b82f6";
    case "joined": return "#22c55e";
  }
}

export function StatusBar({
  connectionStatus,
  captureStatus,
  isWakeLocked,
  participantId,
  roomName,
  captionCount,
  latencyMs,
  p95LatencyMs,
  onDisconnect,
  onStopCapture,
  onOpenDrawer,
  onSaveSession,
}: StatusBarProps) {
  const isLatencyGood = p95LatencyMs !== undefined && p95LatencyMs < 1500;

  return (
    <div className="status-bar" data-testid="status-bar">
      <div className="status-left">
        <div className="status-indicator" data-testid="connection-status">
          <span
            className="status-dot"
            style={{ backgroundColor: statusColor(connectionStatus) }}
          />
          <span className="status-text">{statusLabel(connectionStatus)}</span>
        </div>

        {roomName && (
          <span className="room-badge" data-testid="room-badge">
            Room: {roomName}
          </span>
        )}

        {captureStatus === "active" && (
          <div className="status-indicator mic-active">
            <span className="mic-icon">[MIC]</span>
            <span className="status-text">16kHz Mic</span>
          </div>
        )}

        {isWakeLocked && (
          <div className="status-indicator" title="Screen Wake Lock active">
            <span className="lock-icon">[WAKELOCK]</span>
          </div>
        )}
      </div>

      <div className="status-right">
        {latencyMs !== undefined && (
          <div
            className={`latency-chip ${isLatencyGood ? "good" : "warning"}`}
            title="Real-time measured caption latency (REQ-5 target: <1.5s p95)"
            data-testid="latency-chip"
          >
            <span className="latency-icon"></span>
            <span>{latencyMs}ms</span>
            {p95LatencyMs !== undefined && (
              <span className="p95-label">p95: {p95LatencyMs}ms</span>
            )}
          </div>
        )}

        {captionCount !== undefined && captionCount > 0 && (
          <span className="caption-counter" data-testid="caption-counter">
            {captionCount} {captionCount === 1 ? "caption" : "captions"}
          </span>
        )}
        {participantId && (
          <span className="participant-id">{participantId}</span>
        )}
        {onOpenDrawer && (
          <button
            className="btn btn-sm"
            onClick={onOpenDrawer}
            data-testid="open-drawer-btn"
            title="Open Past Session Archives"
          >
            Archives
          </button>
        )}
        {connectionStatus === "joined" && onSaveSession && (
          <button
            className="btn btn-sm"
            onClick={onSaveSession}
            data-testid="save-session-btn"
            title="Save current meeting to archives"
          >
            Save
          </button>
        )}
        {connectionStatus === "joined" && (
          <button
            className="btn btn-sm btn-danger"
            onClick={() => {
              onStopCapture();
              onDisconnect();
            }}
            data-testid="leave-btn"
          >
            Leave
          </button>
        )}
      </div>
    </div>
  );
}
