/**
 * Tests for CaptionDisplay component rendering.
 *
 * Covers:
 *   - Empty state rendering
 *   - Partial captions render with lower opacity class
 *   - Final captions render with full opacity class
 *   - Grouped view shows speaker sections
 *   - Timeline view shows interleaved entries
 */

import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { CaptionDisplay } from "../components/CaptionDisplay";
import type { CaptionEvent } from "../types";
import type { SpeakerGroup } from "../hooks/useCaptions";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeCaption(overrides: Partial<CaptionEvent> = {}): CaptionEvent {
  return {
    type: "CAPTION",
    segment_id: "seg_1",
    speaker_id: "p_alice",
    speaker_name: "Alice",
    start_ts: 1000,
    end_ts: 2000,
    text: "Hello world",
    is_final: false,
    revision: 1,
    ...overrides,
  };
}

function makeGroups(captions: CaptionEvent[]): SpeakerGroup[] {
  const map = new Map<string, SpeakerGroup>();
  for (const c of captions) {
    let g = map.get(c.speaker_id);
    if (!g) {
      g = { speakerId: c.speaker_id, speakerName: c.speaker_name || c.speaker_id, segments: [] };
      map.set(c.speaker_id, g);
    }
    g.segments.push(c);
  }
  return Array.from(map.values());
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("CaptionDisplay", () => {
  it("renders empty state when no captions", () => {
    render(
      <CaptionDisplay speakerGroups={[]} timeline={[]} viewMode="timeline" />
    );
    expect(screen.getByTestId("caption-display-empty")).toBeInTheDocument();
    expect(screen.getByText(/captions will appear/i)).toBeInTheDocument();
  });

  it("renders partial caption with partial class", () => {
    const partial = makeCaption({ is_final: false, text: "Hel" });
    render(
      <CaptionDisplay
        speakerGroups={makeGroups([partial])}
        timeline={[partial]}
        viewMode="timeline"
      />
    );
    const entry = screen.getByTestId("caption-seg_1");
    expect(entry).toBeInTheDocument();
    expect(entry.className).toContain("partial");
    expect(entry.className).not.toContain("final");
  });

  it("renders final caption with final class", () => {
    const final_ = makeCaption({ is_final: true, text: "Hello world" });
    render(
      <CaptionDisplay
        speakerGroups={makeGroups([final_])}
        timeline={[final_]}
        viewMode="timeline"
      />
    );
    const entry = screen.getByTestId("caption-seg_1");
    expect(entry).toBeInTheDocument();
    expect(entry.className).toContain("final");
  });

  it("renders grouped view with speaker sections", () => {
    const captions = [
      makeCaption({ segment_id: "seg_1", speaker_id: "p_alice", speaker_name: "Alice" }),
      makeCaption({ segment_id: "seg_2", speaker_id: "p_bob", speaker_name: "Bob" }),
    ];

    render(
      <CaptionDisplay
        speakerGroups={makeGroups(captions)}
        timeline={captions}
        viewMode="grouped"
      />
    );

    expect(screen.getByTestId("speaker-p_alice")).toBeInTheDocument();
    expect(screen.getByTestId("speaker-p_bob")).toBeInTheDocument();
  });

  it("renders timeline view with all captions", () => {
    const captions = [
      makeCaption({ segment_id: "seg_1", start_ts: 1000, text: "First" }),
      makeCaption({ segment_id: "seg_2", start_ts: 2000, text: "Second" }),
    ];

    render(
      <CaptionDisplay
        speakerGroups={makeGroups(captions)}
        timeline={captions}
        viewMode="timeline"
      />
    );

    expect(screen.getByTestId("caption-seg_1")).toBeInTheDocument();
    expect(screen.getByTestId("caption-seg_2")).toBeInTheDocument();
  });
});
