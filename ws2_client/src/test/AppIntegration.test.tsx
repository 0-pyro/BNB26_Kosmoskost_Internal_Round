import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import App from "../App";

// Mock useAudioCapture to avoid getUserMedia in jsdom
vi.mock("../hooks/useAudioCapture", () => ({
  useAudioCapture: () => ({
    captureStatus: "idle",
    startCapture: vi.fn().mockResolvedValue(undefined),
    stopCapture: vi.fn(),
  }),
}));

// Mock useWakeLock to avoid navigator.wakeLock in jsdom
vi.mock("../hooks/useWakeLock", () => ({
  useWakeLock: () => ({
    isLocked: false,
    request: vi.fn().mockResolvedValue(undefined),
    release: vi.fn(),
  }),
}));

describe("App End-to-End Integration Flow", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("completes full flow: landing screen -> session archive -> AI assist -> join session -> HUD & captions", async () => {
    // 1. Initial render shows JoinScreen
    render(<App />);

    expect(screen.getByTestId("join-screen")).toBeInTheDocument();
    expect(screen.getByTestId("join-btn")).toBeInTheDocument();
    expect(screen.getByTestId("join-archive-btn")).toBeInTheDocument();

    // 2. Open Session Archives from pre-join screen
    fireEvent.click(screen.getByTestId("join-archive-btn"));

    await waitFor(() => {
      expect(screen.getByTestId("session-drawer")).toBeInTheDocument();
    });

    // Verify session cards
    await waitFor(() => {
      expect(screen.getByTestId("session-card-ROOM_ALPHA_2026")).toBeInTheDocument();
    });

    // 3. Inspect session and test AI Assist inside the static view
    fireEvent.click(screen.getByTestId("session-card-ROOM_ALPHA_2026"));

    await waitFor(() => {
      expect(screen.getByTestId("session-detail-view")).toBeInTheDocument();
    });

    expect(screen.getByTestId("ai-assist-panel")).toBeInTheDocument();
    expect(screen.getByTestId("transcript-log-container")).toBeInTheDocument();

    // Click Summarize in AI Assist
    fireEvent.click(screen.getByTestId("ai-summarize-btn"));
    await waitFor(() => {
      expect(screen.getByTestId("ai-response-box")).toBeInTheDocument();
    });
    expect(screen.getByText(/CORE OBJECTIVE|SUMMARY/i)).toBeInTheDocument();

    // Close the drawer
    fireEvent.click(screen.getByTestId("close-drawer-btn"));
    await waitFor(() => {
      expect(screen.queryByTestId("session-drawer")).toBeNull();
    });

    // 4. Enter participant details and join live room
    const nameInput = screen.getByTestId("name-input");
    fireEvent.change(nameInput, { target: { value: "LeadTester" } });
    fireEvent.click(screen.getByTestId("join-btn"));

    // 5. In-session UI is displayed
    await waitFor(() => {
      expect(screen.getByTestId("app-container")).toBeInTheDocument();
    });

    expect(screen.getByTestId("status-bar")).toBeInTheDocument();
    expect(screen.getByTestId("caption-display-empty")).toBeInTheDocument();
    expect(screen.getByTestId("airtime-hud")).toBeInTheDocument();

    // 6. Test toggles in session view
    fireEvent.click(screen.getByTestId("view-grouped"));
    expect(screen.getByTestId("view-grouped").className).toContain("active");

    fireEvent.click(screen.getByTestId("view-timeline"));
    expect(screen.getByTestId("view-timeline").className).toContain("active");

    // 7. Collapse and expand Airtime HUD
    fireEvent.click(screen.getByTestId("hud-collapse-btn"));
    expect(screen.queryByTestId("airtime-hud")).toBeNull();
    expect(screen.getByTestId("airtime-hud-toggle")).toBeInTheDocument();

    fireEvent.click(screen.getByTestId("airtime-hud-toggle"));
    expect(screen.getByTestId("airtime-hud")).toBeInTheDocument();

    // 8. Open Session Drawer from the StatusBar while in meeting
    fireEvent.click(screen.getByTestId("open-drawer-btn"));
    await waitFor(() => {
      expect(screen.getByTestId("session-drawer")).toBeInTheDocument();
    });
  });
});
