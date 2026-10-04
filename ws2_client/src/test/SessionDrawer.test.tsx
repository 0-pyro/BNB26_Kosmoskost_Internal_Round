import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { SessionDrawer, FALLBACK_SESSIONS, getFallbackSessionDetail } from "../components/SessionDrawer";

describe("SessionDrawer component", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("does not render when isOpen is false", () => {
    const onClose = vi.fn();
    render(<SessionDrawer isOpen={false} onClose={onClose} />);

    expect(screen.queryByTestId("session-drawer")).toBeNull();
  });

  it("renders drawer and displays sessions list", async () => {
    const onClose = vi.fn();
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce({
      ok: true,
      json: async () => FALLBACK_SESSIONS,
    } as Response);

    render(<SessionDrawer isOpen={true} onClose={onClose} />);

    expect(screen.getByTestId("session-drawer")).toBeDefined();
    expect(screen.getByText("SESSION ARCHIVES")).toBeDefined();

    await waitFor(() => {
      expect(screen.getByTestId("session-card-ROOM_ALPHA_2026")).toBeDefined();
    });

    expect(screen.getByText("DSP_SYNC_LAB")).toBeDefined();
    expect(screen.getByText("STANDUP_OCT4")).toBeDefined();

    // Click close button
    fireEvent.click(screen.getByTestId("close-drawer-btn"));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("opens static view and loads transcript and AI Assist when a session is clicked", async () => {
    const onClose = vi.fn();
    const mockDetail = getFallbackSessionDetail("ROOM_ALPHA_2026");

    // 1st fetch: /api/sessions -> list
    // 2nd fetch: /api/sessions/ROOM_ALPHA_2026 -> detail
    vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce({
        ok: true,
        json: async () => FALLBACK_SESSIONS,
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => mockDetail,
      } as Response);

    render(<SessionDrawer isOpen={true} onClose={onClose} />);

    await waitFor(() => {
      expect(screen.getByTestId("session-card-ROOM_ALPHA_2026")).toBeDefined();
    });

    // Click session card
    fireEvent.click(screen.getByTestId("session-card-ROOM_ALPHA_2026"));

    await waitFor(() => {
      expect(screen.getByTestId("session-detail-view")).toBeDefined();
    });

    // Check banner, AI panel, and static transcript
    expect(screen.getByTestId("detail-banner")).toBeDefined();
    expect(screen.getByTestId("ai-assist-panel")).toBeDefined();
    expect(screen.getByTestId("transcript-log-container")).toBeDefined();
    expect(screen.getByText(/validating the multi-device acoustic fusion/i)).toBeDefined();

    // Click Back to Archives
    fireEvent.click(screen.getByTestId("back-to-sessions-btn"));

    await waitFor(() => {
      expect(screen.getByTestId("session-list-view")).toBeDefined();
    });
  });

  it("handles fetch rejection and gracefully uses fallback mock data", async () => {
    const onClose = vi.fn();
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new Error("Network Error"));

    render(<SessionDrawer isOpen={true} onClose={onClose} />);

    await waitFor(() => {
      expect(screen.getByTestId("session-card-ROOM_ALPHA_2026")).toBeDefined();
    });

    fireEvent.click(screen.getByTestId("session-card-ROOM_ALPHA_2026"));

    await waitFor(() => {
      expect(screen.getByTestId("session-detail-view")).toBeDefined();
    });

    expect(screen.getByTestId("transcript-log-container")).toBeDefined();
  });
});
