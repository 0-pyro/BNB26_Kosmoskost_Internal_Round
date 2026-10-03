import { useCallback, useRef, useState } from "react";
import { hashParticipantId } from "../types";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type AudioCaptureStatus = "idle" | "requesting" | "active" | "error";

export interface UseAudioCaptureOptions {
  participantId: string | null;
  onFrame: (frame: ArrayBuffer) => void;
}

export interface UseAudioCaptureReturn {
  captureStatus: AudioCaptureStatus;
  startCapture: () => Promise<void>;
  stopCapture: () => void;
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

/**
 * Manages microphone capture via AudioWorklet.
 *
 * iOS Safari requires a user gesture to create/resume an AudioContext,
 * so `startCapture` must be called from a click/tap handler.
 */
export function useAudioCapture(options: UseAudioCaptureOptions): UseAudioCaptureReturn {
  const { participantId, onFrame } = options;
  const [captureStatus, setCaptureStatus] = useState<AudioCaptureStatus>("idle");

  const contextRef = useRef<AudioContext | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const sourceRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const workletRef = useRef<AudioWorkletNode | null>(null);

  // Keep onFrame callback fresh
  const onFrameRef = useRef(onFrame);
  onFrameRef.current = onFrame;

  const startCapture = useCallback(async () => {
    if (captureStatus === "active" || captureStatus === "requesting") return;

    setCaptureStatus("requesting");

    try {
      // 1. Request microphone (needs user gesture on iOS Safari)
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });
      streamRef.current = stream;

      // 2. Create AudioContext (iOS Safari: must be from user gesture context)
      const ctx = new AudioContext({ sampleRate: 48000 });
      contextRef.current = ctx;

      // Resume in case it was created in suspended state (iOS Safari)
      if (ctx.state === "suspended") {
        await ctx.resume();
      }

      // 3. Load AudioWorklet processor
      await ctx.audioWorklet.addModule("/processor.js");

      // 4. Create worklet node and wire up
      const worklet = new AudioWorkletNode(ctx, "roundtable-processor");
      workletRef.current = worklet;

      // Send participant hash to worklet
      const pidHash = participantId ? hashParticipantId(participantId) : 0;
      worklet.port.postMessage({ type: "init", participantIdHash: pidHash });

      // Listen for completed audio frames
      worklet.port.onmessage = (e: MessageEvent) => {
        if (e.data.type === "audio-frame") {
          onFrameRef.current(e.data.frame);
        }
      };

      // 5. Connect graph: mic -> worklet -> (nowhere, we don't play back)
      const source = ctx.createMediaStreamSource(stream);
      sourceRef.current = source;
      source.connect(worklet);
      // Don't connect worklet to destination (no playback/feedback)

      setCaptureStatus("active");
    } catch (err) {
      console.error("[audio] Failed to start capture", err);
      setCaptureStatus("error");
    }
  }, [captureStatus, participantId]);

  const stopCapture = useCallback(() => {
    // Disconnect worklet
    if (sourceRef.current) {
      sourceRef.current.disconnect();
      sourceRef.current = null;
    }
    if (workletRef.current) {
      workletRef.current.port.close();
      workletRef.current.disconnect();
      workletRef.current = null;
    }

    // Stop microphone stream
    if (streamRef.current) {
      for (const track of streamRef.current.getTracks()) {
        track.stop();
      }
      streamRef.current = null;
    }

    // Close AudioContext
    if (contextRef.current) {
      contextRef.current.close();
      contextRef.current = null;
    }

    setCaptureStatus("idle");
  }, []);

  return {
    captureStatus,
    startCapture,
    stopCapture,
  };
}
