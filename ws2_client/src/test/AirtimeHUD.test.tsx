import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import {
  AirtimeHUD,
  computeSpeakerAirtime,
  generateRetroAsciiBar,
} from "../components/AirtimeHUD";
import type { CaptionEvent } from "../types";

describe("AirtimeHUD utilities", () => {
  it("computes speaker airtime only from finalized segments", () => {
    const events: CaptionEvent[] = [
      {
        type: "CAPTION",
        segment_id: "s1",
        speaker_id: "p1",
        speaker_name: "Alice",
        start_ts: 100,
        end_ts: 200,
        text: "Hello everyone, welcome to the meeting",
        is_final: true,
        revision: 1,
      },
      {
        type: "CAPTION",
        segment_id: "s2",
        speaker_id: "p2",
        speaker_name: "Bob",
        start_ts: 210,
        end_ts: 300,
        text: "Thanks Alice",
        is_final: true,
        revision: 1,
      },
      {
        type: "CAPTION",
        segment_id: "s3",
        speaker_id: "p1",
        speaker_name: "Alice",
        start_ts: 310,
        end_ts: 400,
        text: "Unfinalized partial text here",
        is_final: false,
        revision: 1,
      },
    ];

    const result = computeSpeakerAirtime(events);
    expect(result.speakers).toHaveLength(2);
    expect(result.totalWords).toBe(8); // 6 from Alice ("Hello everyone, welcome to the meeting") + 2 from Bob ("Thanks Alice")

    const alice = result.speakers.find((s) => s.speakerId === "p1");
    const bob = result.speakers.find((s) => s.speakerId === "p2");

    expect(alice).toBeDefined();
    expect(alice?.wordCount).toBe(6);
    expect(alice?.finalSegmentCount).toBe(1);
    expect(alice?.percentage).toBe(75); // 6 / 8 = 75%

    expect(bob).toBeDefined();
    expect(bob?.wordCount).toBe(2);
    expect(bob?.percentage).toBe(25); // 2 / 8 = 25%
  });

  it("handles zero total words without NaN", () => {
    const events: CaptionEvent[] = [
      {
        type: "CAPTION",
        segment_id: "s1",
        speaker_id: "p1",
        speaker_name: "Charlie",
        start_ts: 100,
        end_ts: 200,
        text: "   ",
        is_final: true,
        revision: 1,
      },
    ];

    const result = computeSpeakerAirtime(events);
    expect(result.totalWords).toBe(0);
    expect(result.speakers[0].percentage).toBe(0);
  });

  it("generates correct retro ascii progress bars", () => {
    const full = generateRetroAsciiBar(100, 10);
    expect(full).toBe("██████████");

    const empty = generateRetroAsciiBar(0, 10);
    expect(empty).toBe("░░░░░░░░░░");

    const half = generateRetroAsciiBar(50, 10);
    expect(half).toBe("█████░░░░░");
  });
});

describe("AirtimeHUD component", () => {
  it("renders empty state when there are no finalized captions", () => {
    render(<AirtimeHUD timeline={[]} />);

    expect(screen.getByTestId("airtime-hud")).toBeDefined();
    expect(screen.getByTestId("hud-empty").textContent).toContain("Awaiting finalized speech");
    expect(screen.getByTestId("hud-summary").textContent).toContain("Speakers: 0");
  });

  it("renders speakers with bar chart when finalized captions exist", () => {
    const events: CaptionEvent[] = [
      {
        type: "CAPTION",
        segment_id: "seg_1",
        speaker_id: "spk_1",
        speaker_name: "Alice",
        start_ts: 1000,
        end_ts: 2000,
        text: "Let's review the system architecture and latency budget",
        is_final: true,
        revision: 1,
      },
      {
        type: "CAPTION",
        segment_id: "seg_2",
        speaker_id: "spk_2",
        speaker_name: "Bob",
        start_ts: 2100,
        end_ts: 3000,
        text: "Looks good to me",
        is_final: true,
        revision: 1,
      },
    ];

    render(<AirtimeHUD timeline={events} />);

    expect(screen.getByText(/Alice/)).toBeDefined();
    expect(screen.getByText(/Bob/)).toBeDefined();
    expect(screen.getByTestId("speaker-row-spk_1")).toBeDefined();
    expect(screen.getByTestId("speaker-row-spk_2")).toBeDefined();

    // Check bar fill elements
    const aliceFill = screen.getByTestId("bar-fill-spk_1");
    expect(aliceFill).toBeDefined();
  });

  it("supports collapsing and expanding the HUD overlay", () => {
    render(<AirtimeHUD timeline={[]} defaultExpanded={true} />);

    expect(screen.getByTestId("airtime-hud")).toBeDefined();

    // Collapse HUD
    fireEvent.click(screen.getByTestId("hud-collapse-btn"));
    expect(screen.queryByTestId("airtime-hud")).toBeNull();
    expect(screen.getByTestId("airtime-hud-toggle")).toBeDefined();

    // Expand HUD again
    fireEvent.click(screen.getByTestId("airtime-hud-toggle"));
    expect(screen.getByTestId("airtime-hud")).toBeDefined();
  });
});
