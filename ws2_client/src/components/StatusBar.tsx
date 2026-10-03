import type { ConnectionStatus } from "../hooks/useWebSocket";
import type { AudioCaptureStatus } from "../hooks/useAudioCapture";
import "./StatusBar.css";

interface StatusBarProps {
  connectionStatus: ConnectionStatus;
  captureStatus: AudioCaptureStatus;
  isWakeLocked: boolean;
  participantId: string | null;
  onDisconnect: () => void;
  onStopCapture: () => void;
}

function statusLabel(s: ConnectionStatus): string {
  switch (s) {
    case "disconnected": return "Disconnected";
    case "connecting": return "Connecting…";
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
  onDisconnect,
  onStopCapture,
}: StatusBarProps) {
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

        {captureStatus === "active" && (
          <div className="status-indicator mic-active">
            <span className="mic-icon">🎙️</span>
            <span className="status-text">Recording</span>
          </div>
        )}

        {isWakeLocked && (
          <div className="status-indicator">
            <span className="lock-icon">🔒</span>
          </div>
        )}
      </div>

      <div className="status-right">
        {participantId && (
          <span className="participant-id">{participantId}</span>
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
