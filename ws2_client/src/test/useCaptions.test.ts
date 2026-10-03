/**
 * Tests for useCaptions hook — UI state transitions.
 *
 * Covers:
 *   - Adding a partial caption
 *   - Updating partial -> final (same segment_id)
 *   - Revision ordering (higher revision wins)
 *   - Multiple speakers grouped correctly
 *   - Timeline ordering by start_ts
 *   - History loading
 *   - Clear captions
 */

import { describe, it, expect } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useCaptions } from "../hooks/useCaptions";
import type { CaptionEvent } from "../types";

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

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("useCaptions", () => {
  it("starts with empty state", () => {
    const { result } = renderHook(() => useCaptions());
    expect(result.current.captions.size).toBe(0);
    expect(result.current.speakerGroups).toEqual([]);
    expect(result.current.timeline).toEqual([]);
  });

  it("adds a partial caption", () => {
    const { result } = renderHook(() => useCaptions());
    const partial = makeCaption({ is_final: false, text: "Hel" });

    act(() => {
      result.current.handleCaption(partial);
    });

    expect(result.current.captions.size).toBe(1);
    const stored = result.current.captions.get("seg_1");
    expect(stored).toBeDefined();
    expect(stored!.text).toBe("Hel");
    expect(stored!.is_final).toBe(false);
  });

  it("updates partial to final (same segment_id, same revision)", () => {
    const { result } = renderHook(() => useCaptions());
    const partial = makeCaption({ is_final: false, text: "Hel", revision: 1 });
    const final_ = makeCaption({ is_final: true, text: "Hello world", revision: 1 });

    act(() => {
      result.current.handleCaption(partial);
    });

    expect(result.current.captions.get("seg_1")!.is_final).toBe(false);

    act(() => {
      result.current.handleCaption(final_);
    });

    const stored = result.current.captions.get("seg_1");
    expect(stored!.text).toBe("Hello world");
    expect(stored!.is_final).toBe(true);
    // Should still be only one entry
    expect(result.current.captions.size).toBe(1);
  });

  it("updates partial to final with higher revision", () => {
    const { result } = renderHook(() => useCaptions());
    const partial = makeCaption({ is_final: false, text: "Hel", revision: 1 });
    const final_ = makeCaption({ is_final: true, text: "Hello world", revision: 2 });

    act(() => {
      result.current.handleCaption(partial);
      result.current.handleCaption(final_);
    });

    const stored = result.current.captions.get("seg_1");
    expect(stored!.text).toBe("Hello world");
    expect(stored!.is_final).toBe(true);
    expect(stored!.revision).toBe(2);
  });

  it("rejects older revision", () => {
    const { result } = renderHook(() => useCaptions());
    const newer = makeCaption({ text: "Final text", revision: 3, is_final: true });
    const older = makeCaption({ text: "Old text", revision: 1, is_final: false });

    act(() => {
      result.current.handleCaption(newer);
    });

    act(() => {
      result.current.handleCaption(older);
    });

    const stored = result.current.captions.get("seg_1");
    expect(stored!.text).toBe("Final text");
    expect(stored!.revision).toBe(3);
  });

  it("groups captions by speaker_id", () => {
    const { result } = renderHook(() => useCaptions());
    const aliceCaption = makeCaption({
      segment_id: "seg_1",
      speaker_id: "p_alice",
      speaker_name: "Alice",
      start_ts: 1000,
    });
    const bobCaption = makeCaption({
      segment_id: "seg_2",
      speaker_id: "p_bob",
      speaker_name: "Bob",
      start_ts: 2000,
      text: "Hi Alice",
    });
    const aliceCaption2 = makeCaption({
      segment_id: "seg_3",
      speaker_id: "p_alice",
      speaker_name: "Alice",
      start_ts: 3000,
      text: "How are you?",
    });

    act(() => {
      result.current.handleCaption(aliceCaption);
      result.current.handleCaption(bobCaption);
      result.current.handleCaption(aliceCaption2);
    });

    expect(result.current.speakerGroups.length).toBe(2);

    // Alice's group should come first (start_ts: 1000)
    const aliceGroup = result.current.speakerGroups[0];
    expect(aliceGroup.speakerId).toBe("p_alice");
    expect(aliceGroup.segments.length).toBe(2);
    expect(aliceGroup.segments[0].segment_id).toBe("seg_1");
    expect(aliceGroup.segments[1].segment_id).toBe("seg_3");

    // Bob's group
    const bobGroup = result.current.speakerGroups[1];
    expect(bobGroup.speakerId).toBe("p_bob");
    expect(bobGroup.segments.length).toBe(1);
  });

  it("interleaves captions by start_ts in timeline", () => {
    const { result } = renderHook(() => useCaptions());

    act(() => {
      result.current.handleCaption(
        makeCaption({ segment_id: "seg_1", start_ts: 3000, text: "Third" })
      );
      result.current.handleCaption(
        makeCaption({ segment_id: "seg_2", start_ts: 1000, text: "First" })
      );
      result.current.handleCaption(
        makeCaption({ segment_id: "seg_3", start_ts: 2000, text: "Second" })
      );
    });

    expect(result.current.timeline.length).toBe(3);
    expect(result.current.timeline[0].text).toBe("First");
    expect(result.current.timeline[1].text).toBe("Second");
    expect(result.current.timeline[2].text).toBe("Third");
  });

  it("loads history captions", () => {
    const { result } = renderHook(() => useCaptions());
    const history: CaptionEvent[] = [
      makeCaption({ segment_id: "seg_h1", text: "History 1", start_ts: 100, is_final: true }),
      makeCaption({ segment_id: "seg_h2", text: "History 2", start_ts: 200, is_final: true }),
    ];

    act(() => {
      result.current.loadHistory(history);
    });

    expect(result.current.captions.size).toBe(2);
    expect(result.current.timeline[0].text).toBe("History 1");
    expect(result.current.timeline[1].text).toBe("History 2");
  });

  it("clears all captions", () => {
    const { result } = renderHook(() => useCaptions());

    act(() => {
      result.current.handleCaption(makeCaption());
    });
    expect(result.current.captions.size).toBe(1);

    act(() => {
      result.current.clearCaptions();
    });
    expect(result.current.captions.size).toBe(0);
    expect(result.current.speakerGroups).toEqual([]);
    expect(result.current.timeline).toEqual([]);
  });

  it("handles rapid partial -> partial -> final sequence", () => {
    const { result } = renderHook(() => useCaptions());

    act(() => {
      result.current.handleCaption(
        makeCaption({ text: "H", revision: 1, is_final: false })
      );
    });
    expect(result.current.captions.get("seg_1")!.text).toBe("H");

    act(() => {
      result.current.handleCaption(
        makeCaption({ text: "Hell", revision: 1, is_final: false })
      );
    });
    expect(result.current.captions.get("seg_1")!.text).toBe("Hell");

    act(() => {
      result.current.handleCaption(
        makeCaption({ text: "Hello world", revision: 1, is_final: true })
      );
    });
    expect(result.current.captions.get("seg_1")!.text).toBe("Hello world");
    expect(result.current.captions.get("seg_1")!.is_final).toBe(true);
  });
});
