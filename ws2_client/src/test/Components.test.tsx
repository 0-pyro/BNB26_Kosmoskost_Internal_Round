import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { StatusBar } from "../components/StatusBar";
import { JoinScreen } from "../components/JoinScreen";

describe("StatusBar component", () => {
  it("renders status details, room name, caption count, and latency chip", () => {
    const onDisconnect = vi.fn();
    const onStopCapture = vi.fn();

    render(
      <StatusBar
        connectionStatus="joined"
        captureStatus="active"
        isWakeLocked={true}
        participantId="p_test1"
        roomName="CONF_A"
        captionCount={12}
        latencyMs={185}
        p95LatencyMs={240}
        onDisconnect={onDisconnect}
        onStopCapture={onStopCapture}
      />
    );

    expect(screen.getByText("Live")).toBeDefined();
    expect(screen.getByTestId("room-badge").textContent).toContain("CONF_A");
    expect(screen.getByTestId("caption-counter").textContent).toContain("12");
    expect(screen.getByTestId("latency-chip").textContent).toContain("185ms");
    expect(screen.getByTestId("latency-chip").textContent).toContain("p95: 240ms");

    fireEvent.click(screen.getByTestId("leave-btn"));
    expect(onDisconnect).toHaveBeenCalledTimes(1);
  });

  it("renders and handles onOpenDrawer in StatusBar", () => {
    const onOpenDrawer = vi.fn();
    render(
      <StatusBar
        connectionStatus="joined"
        captureStatus="idle"
        isWakeLocked={false}
        participantId="p1"
        onDisconnect={vi.fn()}
        onStopCapture={vi.fn()}
        onOpenDrawer={onOpenDrawer}
      />
    );

    const btn = screen.getByTestId("open-drawer-btn");
    expect(btn).toBeDefined();
    fireEvent.click(btn);
    expect(onOpenDrawer).toHaveBeenCalledTimes(1);
  });
});

describe("JoinScreen component", () => {
  it("allows entering room, participant, and toggling advanced server URL", () => {
    const onJoin = vi.fn();

    render(<JoinScreen onJoin={onJoin} isConnecting={false} />);

    const sessionInput = screen.getByTestId("session-input");
    const nameInput = screen.getByTestId("name-input");

    fireEvent.change(sessionInput, { target: { value: "DEMO_ROOM" } });
    fireEvent.change(nameInput, { target: { value: "Bob" } });

    // Click advanced settings
    const advancedToggle = screen.getByText(/Advanced: Server URL/i);
    fireEvent.click(advancedToggle);

    // Advanced input should now be visible
    const serverInput = screen.getByTestId("url-input");
    fireEvent.change(serverInput, { target: { value: "ws://127.0.0.1:8000/ws" } });

    fireEvent.click(screen.getByTestId("join-btn"));

    expect(onJoin).toHaveBeenCalledWith("DEMO_ROOM", "Bob", "ws://127.0.0.1:8000/ws");
  });

  it("renders and handles past sessions button in JoinScreen", () => {
    const onOpenDrawer = vi.fn();
    render(<JoinScreen onJoin={vi.fn()} isConnecting={false} onOpenDrawer={onOpenDrawer} />);

    const btn = screen.getByTestId("join-archive-btn");
    expect(btn).toBeDefined();
    fireEvent.click(btn);
    expect(onOpenDrawer).toHaveBeenCalledTimes(1);
  });
});

