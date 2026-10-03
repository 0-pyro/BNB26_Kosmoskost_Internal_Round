import { useState } from "react";
import "./JoinScreen.css";

interface JoinScreenProps {
  onJoin: (sessionId: string, name: string) => void;
  isConnecting: boolean;
}

export function JoinScreen({ onJoin, isConnecting }: JoinScreenProps) {
  const [sessionId, setSessionId] = useState("ROOM1");
  const [name, setName] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!sessionId.trim() || !name.trim()) return;
    onJoin(sessionId.trim(), name.trim());
  };

  return (
    <div className="join-screen" data-testid="join-screen">
      <div className="join-card">
        <div className="join-logo">
          <span className="logo-icon">🎙️</span>
          <h1 className="logo-text">Roundtable</h1>
          <p className="logo-sub">Live Captioning</p>
        </div>

        <form className="join-form" onSubmit={handleSubmit}>
          <div className="field">
            <label htmlFor="session-id">Room Code</label>
            <input
              id="session-id"
              type="text"
              value={sessionId}
              onChange={(e) => setSessionId(e.target.value)}
              placeholder="e.g. ROOM1"
              autoFocus
              data-testid="session-input"
            />
          </div>

          <div className="field">
            <label htmlFor="participant-name">Your Name</label>
            <input
              id="participant-name"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Alice"
              data-testid="name-input"
            />
          </div>

          <button
            type="submit"
            className="btn btn-primary btn-join"
            disabled={!sessionId.trim() || !name.trim() || isConnecting}
            data-testid="join-btn"
          >
            {isConnecting ? "Connecting…" : "Join Session"}
          </button>
        </form>
      </div>
    </div>
  );
}
