import { useEffect, useRef, useState } from "react";
import type { CaptionEvent } from "../types";
import type { SpeakerGroup } from "../hooks/useCaptions";
import "./CaptionDisplay.css";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface CaptionDisplayProps {
  speakerGroups: SpeakerGroup[];
  timeline: CaptionEvent[];
  /** "grouped" = group by speaker; "timeline" = interleave by start_ts */
  viewMode: "grouped" | "timeline";
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

export function formatCaptionTimestamp(ts?: number): string {
  if (ts === undefined || ts === null || isNaN(ts) || ts <= 0) {
    return "00:00";
  }
  if (ts > 1_000_000_000_000) {
    const d = new Date(ts);
    return d.toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
    });
  }
  if (ts > 1_000_000_000) {
    const d = new Date(ts * 1000);
    return d.toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
    });
  }
  const totalSeconds = Math.max(0, Math.floor(ts / 1000));
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes.toString().padStart(2, "0")}:${seconds.toString().padStart(2, "0")}`;
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function CaptionBubble({ caption }: { caption: CaptionEvent }) {
  const tsStr = formatCaptionTimestamp(caption.start_ts || caption.end_ts);

  return (
    <div
      className={`caption-bubble ${caption.is_final ? "final" : "partial"}`}
      data-segment-id={caption.segment_id}
      data-testid={`caption-${caption.segment_id}`}
    >
      <div className="caption-bubble-meta">
        <span
          className="caption-timestamp"
          data-testid={`bubble-time-${caption.segment_id}`}
        >
          [{tsStr}]
        </span>
      </div>
      <span className="caption-text">{caption.text}</span>
      {!caption.is_final && <span className="partial-indicator">●</span>}
    </div>
  );
}

function SpeakerSection({ group }: { group: SpeakerGroup }) {
  // Generate a deterministic hue from speaker ID for the accent color
  let hue = 0;
  for (let i = 0; i < group.speakerId.length; i++) {
    hue = (hue * 31 + group.speakerId.charCodeAt(i)) % 360;
  }

  const latestSegment = group.segments[group.segments.length - 1];
  const lastActiveTs = latestSegment
    ? formatCaptionTimestamp(latestSegment.start_ts || latestSegment.end_ts)
    : "";

  return (
    <div className="speaker-section" data-testid={`speaker-${group.speakerId}`}>
      <div className="speaker-header">
        <div
          className="speaker-avatar"
          style={{ backgroundColor: `hsl(${hue}, 65%, 55%)` }}
        >
          {group.speakerName.charAt(0).toUpperCase()}
        </div>
        <span className="speaker-name">{group.speakerName}</span>
        {lastActiveTs && (
          <span
            className="speaker-last-active"
            data-testid={`speaker-time-${group.speakerId}`}
          >
            [{lastActiveTs}]
          </span>
        )}
      </div>
      <div className="speaker-captions">
        {group.segments.map((caption) => (
          <CaptionBubble key={caption.segment_id} caption={caption} />
        ))}
      </div>
    </div>
  );
}

function TimelineEntry({ caption }: { caption: CaptionEvent }) {
  let hue = 0;
  for (let i = 0; i < caption.speaker_id.length; i++) {
    hue = (hue * 31 + caption.speaker_id.charCodeAt(i)) % 360;
  }

  const tsStr = formatCaptionTimestamp(caption.start_ts || caption.end_ts);

  return (
    <div
      className={`timeline-entry ${caption.is_final ? "final" : "partial"}`}
      data-testid={`caption-${caption.segment_id}`}
    >
      <div
        className="timeline-dot"
        style={{ backgroundColor: `hsl(${hue}, 65%, 55%)` }}
      />
      <div className="timeline-content">
        <div className="timeline-header">
          <span className="timeline-speaker">
            {caption.speaker_name || caption.speaker_id}
          </span>
          <span
            className="timeline-timestamp"
            data-testid={`timestamp-${caption.segment_id}`}
          >
            [{tsStr}]
          </span>
        </div>
        <span className="timeline-text">{caption.text}</span>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function CaptionDisplay({ speakerGroups, timeline, viewMode }: CaptionDisplayProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const isAutoScrollActiveRef = useRef(true);
  const [showScrollBottomBtn, setShowScrollBottomBtn] = useState(false);

  // Monitor user scrolling: if user scrolls up > 60px from bottom, pause autoscroll
  const handleScroll = () => {
    if (!containerRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = containerRef.current;
    const isAtBottom = scrollHeight - scrollTop - clientHeight < 60;
    isAutoScrollActiveRef.current = isAtBottom;
    setShowScrollBottomBtn(!isAtBottom);
  };

  const scrollToBottom = () => {
    if (containerRef.current) {
      containerRef.current.scrollTo({
        top: containerRef.current.scrollHeight,
        behavior: "smooth",
      });
      isAutoScrollActiveRef.current = true;
      setShowScrollBottomBtn(false);
    }
  };

  // Whenever new captions arrive or view switches, autoscroll if active
  useEffect(() => {
    if (isAutoScrollActiveRef.current && containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [timeline, speakerGroups, viewMode]);

  if (timeline.length === 0) {
    return (
      <div className="caption-display empty" data-testid="caption-display-empty">
        <div className="empty-state">
          <div className="empty-icon">[AWAITING AUDIO]</div>
          <p>Captions will appear here...</p>
        </div>
      </div>
    );
  }

  return (
    <div
      className="caption-display"
      data-testid="caption-display"
      ref={containerRef}
      onScroll={handleScroll}
    >
      {viewMode === "grouped" ? (
        <div className="grouped-view">
          {speakerGroups.map((group) => (
            <SpeakerSection key={group.speakerId} group={group} />
          ))}
        </div>
      ) : (
        <div className="timeline-view">
          {timeline.map((caption) => (
            <TimelineEntry key={caption.segment_id} caption={caption} />
          ))}
        </div>
      )}
      {showScrollBottomBtn && (
        <button
          className="btn-scroll-bottom"
          onClick={scrollToBottom}
          title="Scroll to latest captions"
        >
          [v LATEST CAPTIONS]
        </button>
      )}
    </div>
  );
}
