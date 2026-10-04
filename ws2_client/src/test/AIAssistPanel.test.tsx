import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { AIAssistPanel, formatTranscriptForAI } from "../components/AIAssistPanel";
import type { CaptionEvent } from "../types";

describe("AIAssistPanel utilities", () => {
  it("formats transcript text correctly for AI prompt context", () => {
    const timeline: CaptionEvent[] = [
      {
        type: "CAPTION",
        segment_id: "s1",
        speaker_id: "spk_1",
        speaker_name: "Alice",
        start_ts: 1000,
        end_ts: 2000,
        text: "AudioWorklet running at 16kHz.",
        is_final: true,
        revision: 1,
      },
      {
        type: "CAPTION",
        segment_id: "s2",
        speaker_id: "spk_2",
        speaker_name: "Bob",
        start_ts: 2200,
        end_ts: 3000,
        text: "Partial text here",
        is_final: false,
        revision: 1,
      },
      {
        type: "CAPTION",
        segment_id: "s3",
        speaker_id: "spk_2",
        speaker_name: "Bob",
        start_ts: 3100,
        end_ts: 4000,
        text: "GCC-PHAT alignment verified.",
        is_final: true,
        revision: 1,
      },
    ];

    const formatted = formatTranscriptForAI(timeline);
    expect(formatted).toContain("[Alice]: AudioWorklet running at 16kHz.");
    expect(formatted).toContain("[Bob]: GCC-PHAT alignment verified.");
    expect(formatted).not.toContain("Partial text here");
  });
});

describe("AIAssistPanel component", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("renders assist buttons and query form", () => {
    render(<AIAssistPanel sessionId="ROOM_TEST" />);

    expect(screen.getByTestId("ai-assist-panel")).toBeDefined();
    expect(screen.getByTestId("ai-summarize-btn")).toBeDefined();
    expect(screen.getByTestId("ai-translate-btn")).toBeDefined();
    expect(screen.getByTestId("ai-custom-query-input")).toBeDefined();
    expect(screen.getByTestId("ai-query-btn")).toBeDefined();
  });

  it("triggers summarize action and displays response", async () => {
    // Mock fetch for /api/ai/assist
    const mockResponse = { result: "Key discussion point: Latency below 100ms." };
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse,
    } as Response);

    render(<AIAssistPanel sessionId="ROOM_TEST" />);

    fireEvent.click(screen.getByTestId("ai-summarize-btn"));

    await waitFor(() => {
      expect(screen.getByTestId("ai-response-box")).toBeDefined();
    });

    expect(screen.getByText(/Key discussion point: Latency below 100ms/)).toBeDefined();

    // Clear response
    fireEvent.click(screen.getByTestId("ai-clear-btn"));
    expect(screen.queryByTestId("ai-response-box")).toBeNull();
  });

  it("triggers translation and handles fallback if endpoint fails", async () => {
    // Simulate endpoint 404 or failure
    vi.spyOn(globalThis, "fetch").mockRejectedValueOnce(new Error("Network Error / 404"));

    render(<AIAssistPanel sessionId="ROOM_TEST" />);

    fireEvent.click(screen.getByTestId("ai-translate-btn"));

    await waitFor(() => {
      expect(screen.getByTestId("ai-response-box")).toBeDefined();
    });

    // Should render rich fallback translation
    expect(screen.getByText(/TRANSLATION: SPANISH/i)).toBeDefined();
  });

  it("submits custom query and displays response", async () => {
    const mockResponse = { result: "Alice spoke 65% of the total words." };
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse,
    } as Response);

    render(<AIAssistPanel sessionId="ROOM_TEST" />);

    const input = screen.getByTestId("ai-custom-query-input");
    fireEvent.change(input, { target: { value: "Who spoke the most?" } });
    fireEvent.click(screen.getByTestId("ai-query-btn"));

    await waitFor(() => {
      expect(screen.getByTestId("ai-response-box")).toBeDefined();
    });

    expect(screen.getByText(/Alice spoke 65% of the total words/)).toBeDefined();
  });
});
