import { useCallback, useState } from "react";
import type { CaptionEvent } from "../types";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/** A speaker group with their ordered captions. */
export interface SpeakerGroup {
  speakerId: string;
  speakerName: string;
  segments: CaptionEvent[];
}

export interface UseCaptionsReturn {
  /** All caption events, keyed by segment_id (latest revision wins). */
  captions: Map<string, CaptionEvent>;
  /** Speaker groups sorted by earliest start_ts. */
  speakerGroups: SpeakerGroup[];
  /** Interleaved captions ordered by start_ts. */
  timeline: CaptionEvent[];
  /** Process an incoming CaptionEvent. */
  handleCaption: (event: CaptionEvent) => void;
  /** Load history captions (e.g. from JoinAck). */
  loadHistory: (events: CaptionEvent[]) => void;
  /** Clear all captions. */
  clearCaptions: () => void;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function buildSpeakerGroups(captions: Map<string, CaptionEvent>): SpeakerGroup[] {
  const groups = new Map<string, SpeakerGroup>();

  for (const caption of captions.values()) {
    let group = groups.get(caption.speaker_id);
    if (!group) {
      group = {
        speakerId: caption.speaker_id,
        speakerName: caption.speaker_name || caption.speaker_id,
        segments: [],
      };
      groups.set(caption.speaker_id, group);
    }
    // Update speaker name if we get a non-empty one
    if (caption.speaker_name) {
      group.speakerName = caption.speaker_name;
    }
    group.segments.push(caption);
  }

  // Sort segments within each group by start_ts
  for (const group of groups.values()) {
    group.segments.sort((a, b) => a.start_ts - b.start_ts);
  }

  // Sort groups by earliest start_ts of their first segment
  return Array.from(groups.values()).sort((a, b) => {
    const aTs = a.segments[0]?.start_ts ?? 0;
    const bTs = b.segments[0]?.start_ts ?? 0;
    return aTs - bTs;
  });
}

function buildTimeline(captions: Map<string, CaptionEvent>): CaptionEvent[] {
  return Array.from(captions.values()).sort((a, b) => a.start_ts - b.start_ts);
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useCaptions(): UseCaptionsReturn {
  const [captions, setCaptions] = useState<Map<string, CaptionEvent>>(new Map());

  const handleCaption = useCallback((event: CaptionEvent) => {
    setCaptions((prev) => {
      const existing = prev.get(event.segment_id);
      // Only update if revision is newer or equal (latest write wins)
      if (existing && existing.revision > event.revision) {
        return prev;
      }
      const next = new Map(prev);
      next.set(event.segment_id, event);
      return next;
    });
  }, []);

  const loadHistory = useCallback((events: CaptionEvent[]) => {
    setCaptions((prev) => {
      const next = new Map(prev);
      for (const event of events) {
        const existing = next.get(event.segment_id);
        if (!existing || existing.revision <= event.revision) {
          next.set(event.segment_id, event);
        }
      }
      return next;
    });
  }, []);

  const clearCaptions = useCallback(() => {
    setCaptions(new Map());
  }, []);

  const speakerGroups = buildSpeakerGroups(captions);
  const timeline = buildTimeline(captions);

  return {
    captions,
    speakerGroups,
    timeline,
    handleCaption,
    loadHistory,
    clearCaptions,
  };
}
