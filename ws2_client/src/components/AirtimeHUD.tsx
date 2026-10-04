import { useState, useMemo } from "react";
import type { CaptionEvent, SpeakerAirtime } from "../types";
import "./AirtimeHUD.css";

export interface AirtimeHUDProps {
  timeline: CaptionEvent[];
  isDocked?: boolean;
  className?: string;
  defaultExpanded?: boolean;
}

/**
 * Computes airtime metrics per speaker from finalized caption events.
 */
export function computeSpeakerAirtime(timeline: CaptionEvent[]): {
  speakers: SpeakerAirtime[];
  totalWords: number;
  totalChars: number;
} {
  const finalSegments = timeline.filter((seg) => seg.is_final);
  const statsMap = new Map<
    string,
    {
      speakerId: string;
      speakerName: string;
      wordCount: number;
      charCount: number;
      finalSegmentCount: number;
    }
  >();

  let totalWords = 0;
  let totalChars = 0;

  for (const seg of finalSegments) {
    const trimmed = seg.text.trim();
    const words = trimmed ? trimmed.split(/\s+/).filter(Boolean).length : 0;
    const chars = trimmed.length;

    totalWords += words;
    totalChars += chars;

    const existing = statsMap.get(seg.speaker_id);
    if (!existing) {
      statsMap.set(seg.speaker_id, {
        speakerId: seg.speaker_id,
        speakerName: seg.speaker_name || seg.speaker_id,
        wordCount: words,
        charCount: chars,
        finalSegmentCount: 1,
      });
    } else {
      if (seg.speaker_name) {
        existing.speakerName = seg.speaker_name;
      }
      existing.wordCount += words;
      existing.charCount += chars;
      existing.finalSegmentCount += 1;
    }
  }

  const speakers: SpeakerAirtime[] = Array.from(statsMap.values())
    .map((stat) => ({
      ...stat,
      percentage:
        totalWords > 0
          ? Math.round((stat.wordCount / totalWords) * 100)
          : 0,
    }))
    .sort((a, b) => b.wordCount - a.wordCount);

  return { speakers, totalWords, totalChars };
}

/**
 * Generates an ASCII terminal progress bar.
 */
export function generateRetroAsciiBar(percentage: number, totalBlocks = 12): string {
  const filled = Math.min(totalBlocks, Math.max(0, Math.round((percentage / 100) * totalBlocks)));
  const empty = Math.max(0, totalBlocks - filled);
  return "█".repeat(filled) + "░".repeat(empty);
}

export function AirtimeHUD({
  timeline,
  isDocked = true,
  className = "",
  defaultExpanded = true,
}: AirtimeHUDProps) {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);

  const { speakers, totalWords, totalChars } = useMemo(
    () => computeSpeakerAirtime(timeline),
    [timeline]
  );

  if (!isExpanded) {
    return (
      <button
        className={`airtime-hud-collapsed ${isDocked ? "docked" : ""} ${className}`}
        onClick={() => setIsExpanded(true)}
        data-testid="airtime-hud-toggle"
        title="Open Speaker Airtime HUD"
      >
        <span className="hud-pulse-dot" />
        <span>AIRTIME HUD ({speakers.length})</span>
      </button>
    );
  }

  return (
    <div
      className={`airtime-hud ${isDocked ? "docked" : ""} ${className}`}
      data-testid="airtime-hud"
    >
      <div
        className="airtime-hud-header"
        onClick={() => setIsExpanded(false)}
        role="button"
        tabIndex={0}
        aria-label="Collapse Airtime HUD"
      >
        <div className="hud-title-wrap">
          <span className="hud-pulse-dot" />
          <span className="hud-title">AIRTIME HUD [LIVE]</span>
        </div>
        <div className="hud-actions">
          <button
            className="hud-btn"
            onClick={(e) => {
              e.stopPropagation();
              setIsExpanded(false);
            }}
            data-testid="hud-collapse-btn"
            aria-label="Minimize HUD"
          >
            [-]
          </button>
        </div>
      </div>

      <div className="airtime-hud-body" data-testid="airtime-hud-body">
        <div className="hud-stats-summary" data-testid="hud-summary">
          <span>Speakers: {speakers.length}</span>
          <span>Words: {totalWords} ({totalChars}c)</span>
        </div>

        {speakers.length === 0 ? (
          <div className="hud-empty-state" data-testid="hud-empty">
            &gt; Awaiting finalized speech segments...
          </div>
        ) : (
          speakers.map((speaker) => (
            <div
              key={speaker.speakerId}
              className="speaker-airtime-row"
              data-testid={`speaker-row-${speaker.speakerId}`}
            >
              <div className="speaker-meta">
                <span className="speaker-label" title={speaker.speakerName}>
                  [{speaker.speakerName}]
                </span>
                <span className="speaker-numbers">
                  {speaker.wordCount}w ({speaker.percentage}%)
                </span>
              </div>

              {/* Terminal ASCII Bar for retro feel */}
              <div
                className="retro-ascii-bar"
                data-testid={`ascii-bar-${speaker.speakerId}`}
                style={{
                  fontFamily: "monospace",
                  letterSpacing: "-1px",
                  fontSize: "0.85rem",
                  color: "var(--accent)",
                }}
              >
                {generateRetroAsciiBar(speaker.percentage, 16)}{" "}
                <span style={{ fontSize: "0.8rem", opacity: 0.9 }}>
                  {speaker.percentage}%
                </span>
              </div>

              {/* Graphical bar track with scanline texture */}
              <div className="airtime-bar-track">
                <div
                  className="airtime-bar-fill"
                  style={{ width: `${Math.max(speaker.percentage, 3)}%` }}
                  data-testid={`bar-fill-${speaker.speakerId}`}
                >
                  <div className="airtime-bar-pattern" />
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
