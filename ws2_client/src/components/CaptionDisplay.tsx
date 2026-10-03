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
// Sub-components
// ---------------------------------------------------------------------------

function CaptionBubble({ caption }: { caption: CaptionEvent }) {
  return (
    <div
      className={`caption-bubble ${caption.is_final ? "final" : "partial"}`}
      data-segment-id={caption.segment_id}
      data-testid={`caption-${caption.segment_id}`}
    >
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
        <span className="timeline-speaker">
          {caption.speaker_name || caption.speaker_id}
        </span>
        <span className="timeline-text">{caption.text}</span>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function CaptionDisplay({ speakerGroups, timeline, viewMode }: CaptionDisplayProps) {
  if (timeline.length === 0) {
    return (
      <div className="caption-display empty" data-testid="caption-display-empty">
        <div className="empty-state">
          <div className="empty-icon">💬</div>
          <p>Captions will appear here…</p>
        </div>
      </div>
    );
  }

  return (
    <div className="caption-display" data-testid="caption-display">
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
    </div>
  );
}
