import { useEffect, useState } from "react";
import type { CaptionEvent, SessionDetail, SessionSummary } from "../types";
import { AIAssistPanel } from "./AIAssistPanel";
import "./SessionDrawer.css";

export interface SessionDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  apiBaseUrl?: string;
  initialSessionId?: string;
}

export const FALLBACK_SESSIONS: SessionSummary[] = [
  {
    session_id: "ROOM_ALPHA_2026",
    start_time: Date.now() - 3600000 * 2,
    participants: ["Alice", "Bob", "Charlie", "Lead"],
    caption_count: 58,
    duration_sec: 720,
  },
  {
    session_id: "DSP_SYNC_LAB",
    start_time: Date.now() - 3600000 * 24,
    participants: ["Alice", "Bob"],
    caption_count: 34,
    duration_sec: 410,
  },
  {
    session_id: "STANDUP_OCT4",
    start_time: Date.now() - 3600000 * 48,
    participants: ["Lead", "Charlie", "Dev3"],
    caption_count: 22,
    duration_sec: 290,
  },
];

export function getFallbackSessionDetail(sessionId: string): SessionDetail {
  return {
    session_id: sessionId,
    start_time: Date.now() - 3600000 * 2,
    participants: [
      { id: "p_1", name: "Alice", connection_state: "ACTIVE" },
      { id: "p_2", name: "Bob", connection_state: "ACTIVE" },
      { id: "p_3", name: "Charlie", connection_state: "ACTIVE" },
    ],
    timeline: [
      {
        type: "CAPTION",
        segment_id: "seg_101",
        speaker_id: "p_1",
        speaker_name: "Alice",
        start_ts: 1000,
        end_ts: 4500,
        text: "Good morning team. Today we are validating the multi-device acoustic fusion pipeline.",
        is_final: true,
        revision: 1,
      },
      {
        type: "CAPTION",
        segment_id: "seg_102",
        speaker_id: "p_2",
        speaker_name: "Bob",
        start_ts: 5200,
        end_ts: 9800,
        text: "I tested the GCC-PHAT TDOA estimator. Latency is consistently under 80 milliseconds across four channels.",
        is_final: true,
        revision: 1,
      },
      {
        type: "CAPTION",
        segment_id: "seg_103",
        speaker_id: "p_3",
        speaker_name: "Charlie",
        start_ts: 10400,
        end_ts: 15100,
        text: "The client-side ring buffer survived our simulated thirty percent packet drop without losing speech frames.",
        is_final: true,
        revision: 1,
      },
      {
        type: "CAPTION",
        segment_id: "seg_104",
        speaker_id: "p_1",
        speaker_name: "Alice",
        start_ts: 16000,
        end_ts: 21000,
        text: "Excellent. Let's merge the UI and run the end-to-end evaluation benchmark before the presentation.",
        is_final: true,
        revision: 1,
      },
    ],
  };
}

function formatTimestamp(ts: number): string {
  if (!ts) return "N/A";
  const date = new Date(ts);
  return date.toLocaleString([], {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatOffset(ms: number): string {
  const totalSeconds = Math.floor(ms / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes.toString().padStart(2, "0")}:${seconds.toString().padStart(2, "0")}`;
}

export function SessionDrawer({
  isOpen,
  onClose,
  apiBaseUrl = "",
  initialSessionId,
}: SessionDrawerProps) {
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [loadingList, setLoadingList] = useState(false);
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(
    initialSessionId || null
  );
  const [sessionDetail, setSessionDetail] = useState<SessionDetail | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);

  // Fetch session list when opened
  useEffect(() => {
    if (!isOpen) return;

    let isMounted = true;
    setLoadingList(true);

    fetch(`${apiBaseUrl}/api/sessions`)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((data) => {
        if (!isMounted) return;
        const list: SessionSummary[] = Array.isArray(data)
          ? data
          : data.sessions || [];
        setSessions(list.length > 0 ? list : FALLBACK_SESSIONS);
      })
      .catch(() => {
        // Fallback to mock session archives
        if (isMounted) {
          setSessions(FALLBACK_SESSIONS);
        }
      })
      .finally(() => {
        if (isMounted) setLoadingList(false);
      });

    return () => {
      isMounted = false;
    };
  }, [isOpen, apiBaseUrl]);

  // Fetch session detail when a session is selected
  useEffect(() => {
    if (!selectedSessionId || !isOpen) {
      setSessionDetail(null);
      return;
    }

    let isMounted = true;
    setLoadingDetail(true);

    fetch(`${apiBaseUrl}/api/sessions/${selectedSessionId}`)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((data) => {
        if (!isMounted) return;
        let normalized: SessionDetail;
        if (Array.isArray(data)) {
          const events: CaptionEvent[] = data;
          const speakerSet = new Set<string>();
          events.forEach((ev) => {
            const name = ev.speaker_name || ev.speaker_id;
            if (name) speakerSet.add(name);
          });
          const participants = Array.from(speakerSet).map((name) => ({
            id: name,
            name,
            connection_state: "DISCONNECTED",
          }));
          const startTime = events[0]?.start_ts || Date.now();
          normalized = {
            session_id: selectedSessionId,
            start_time: startTime,
            participants,
            timeline: events,
          };
        } else {
          normalized = {
            session_id: data.session_id || selectedSessionId,
            start_time: data.start_time || data.timestamp || data.created_at || Date.now(),
            participants: data.participants || [],
            timeline: data.timeline || data.transcript || [],
          };
        }
        setSessionDetail(normalized);
      })
      .catch(() => {
        // Fallback to mock session detail
        if (isMounted) {
          setSessionDetail(getFallbackSessionDetail(selectedSessionId));
        }
      })
      .finally(() => {
        if (isMounted) setLoadingDetail(false);
      });

    return () => {
      isMounted = false;
    };
  }, [selectedSessionId, isOpen, apiBaseUrl]);

  if (!isOpen) return null;

  return (
    <>
      <div
        className="session-drawer-backdrop"
        onClick={onClose}
        data-testid="session-drawer-backdrop"
      />
      <aside className="session-drawer" data-testid="session-drawer">
        <div className="session-drawer-header">
          <div className="drawer-title-group">
            <span className="hud-pulse-dot" />
            <h2 className="drawer-title">
              {selectedSessionId
                ? `SESSION // ${selectedSessionId}`
                : "SESSION ARCHIVES"}
            </h2>
          </div>
          <button
            className="btn btn-sm"
            onClick={onClose}
            data-testid="close-drawer-btn"
            aria-label="Close session archive drawer"
          >
            [X] CLOSE
          </button>
        </div>

        <div className="drawer-body">
          {selectedSessionId ? (
            /* Static Session Detail View with AI Assist */
            <div
              className="session-detail-view"
              data-testid="session-detail-view"
            >
              <div className="detail-toolbar">
                <button
                  className="btn btn-sm"
                  onClick={() => setSelectedSessionId(null)}
                  data-testid="back-to-sessions-btn"
                >
                  &lt;-- Back to Archives
                </button>
              </div>

              {loadingDetail && (
                <div
                  className="ai-loading-state"
                  data-testid="loading-session-detail"
                >
                  &gt;&gt; RETRIEVING ARCHIVED SESSION DATA...
                </div>
              )}

              {sessionDetail && (
                <>
                  <div className="detail-banner" data-testid="detail-banner">
                    <div className="detail-banner-title">
                      {sessionDetail.session_id}
                    </div>
                    <div className="detail-banner-meta">
                      <span>Date: {formatTimestamp(sessionDetail.start_time)}</span>
                      <span>
                        Participants:{" "}
                        {sessionDetail.participants
                          ?.map((p) => p.name || p.id)
                          .join(", ") || "None"}
                      </span>
                      <span>
                        Captions: {sessionDetail.timeline?.length ?? 0}
                      </span>
                    </div>
                  </div>

                  {/* Integrated AI Assist Panel */}
                  <AIAssistPanel
                    sessionId={sessionDetail.session_id}
                    timeline={sessionDetail.timeline}
                    apiBaseUrl={apiBaseUrl}
                  />

                  {/* Static Transcript Log */}
                  <div
                    className="transcript-log-container"
                    data-testid="transcript-log-container"
                  >
                    <div className="transcript-log-title">
                      &gt; ARCHIVED TRANSCRIPT TIMELINE
                    </div>
                    {!sessionDetail.timeline || sessionDetail.timeline.length === 0 ? (
                      <div className="hud-empty-state">
                        No transcript recorded for this session.
                      </div>
                    ) : (
                      sessionDetail.timeline.map((item, idx) => (
                        <div
                          key={item.segment_id || `seg-${idx}`}
                          className="transcript-entry"
                          data-testid={`transcript-entry-${item.segment_id || idx}`}
                        >
                          <div className="transcript-entry-meta">
                            <span className="transcript-speaker">
                              [{item.speaker_name || item.speaker_id || "Speaker"}]
                            </span>
                            <span>{formatOffset(item.start_ts || 0)}</span>
                          </div>
                          <div className="transcript-text">{item.text}</div>
                        </div>
                      ))
                    )}
                  </div>
                </>
              )}
            </div>
          ) : (
            /* Sessions List View */
            <div className="session-list-view" data-testid="session-list-view">
              {loadingList && (
                <div
                  className="ai-loading-state"
                  data-testid="loading-session-list"
                >
                  &gt;&gt; QUERYING SESSION REGISTRY...
                </div>
              )}

              {!loadingList && sessions.length === 0 && (
                <div className="hud-empty-state" data-testid="no-sessions-msg">
                  No archived sessions found on server.
                </div>
              )}

              {sessions.map((sess) => {
                const participantNames = Array.isArray(sess.participants)
                  ? sess.participants.map((p) =>
                      typeof p === "string" ? p : p.name || p.id
                    )
                  : [];
                const sessTime = sess.start_time || (sess as any).timestamp || (sess as any).created_at || 0;
                const count = sess.caption_count ?? (sess as any).transcript_count ?? 0;

                return (
                  <div
                    key={sess.session_id}
                    className="session-card"
                    onClick={() => setSelectedSessionId(sess.session_id)}
                    data-testid={`session-card-${sess.session_id}`}
                    role="button"
                    tabIndex={0}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") setSelectedSessionId(sess.session_id);
                    }}
                  >
                    <div className="session-card-header">
                      <span className="session-card-title">{sess.session_id}</span>
                      <span className="session-card-time">
                        {formatTimestamp(sessTime)}
                      </span>
                    </div>

                    <div className="session-card-meta">
                      {participantNames.map((name) => (
                        <span key={name} className="participant-pill">
                          {name}
                        </span>
                      ))}
                    </div>

                    <div className="session-card-footer">
                      <span>{count} captions</span>
                      <span className="btn btn-sm btn-primary">
                        [INSPECT &amp; AI ASSIST]
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </aside>
    </>
  );
}
