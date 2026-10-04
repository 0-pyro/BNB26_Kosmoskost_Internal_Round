/**
 * Roundtable Protocol Types (v1.0)
 *
 * TypeScript equivalents of the authoritative contracts in contracts/models.py.
 * DO NOT modify the contracts; update here only if the contracts change.
 *
 * Binary audio frame layout (big-endian, 16 bytes total):
 *   [0:1]  Magic 0xAA 0xBB
 *   [2:3]  Participant ID Hash (UInt16)
 *   [4:7]  SeqNum (UInt32)
 *   [8:15] CaptureTS (UInt64, ms since epoch)
 */

// ---------------------------------------------------------------------------
// Client -> Server messages
// ---------------------------------------------------------------------------

export interface JoinRequest {
  type: "JOIN";
  session_id: string;
  participant_name: string;
  participant_id?: string;
}

export interface TimeSyncRequest {
  type: "SYNC";
  client_tx_ts: number; // milliseconds since epoch
}

// ---------------------------------------------------------------------------
// Server -> Client messages
// ---------------------------------------------------------------------------

export interface CaptionEvent {
  type: "CAPTION";
  segment_id: string;
  speaker_id: string;
  speaker_name: string;
  start_ts: number;    // session-relative ms
  end_ts: number;      // session-relative ms
  text: string;
  is_final: boolean;
  revision: number;
}

export interface JoinAck {
  type: "JOIN_ACK";
  participant_id: string;
  history: CaptionEvent[];
}

export interface TimeSyncResponse {
  type: "SYNC_ACK";
  client_tx_ts: number;
  server_rx_ts: number;
  server_tx_ts: number;
}

// Union of all server messages
export type ServerMessage = CaptionEvent | JoinAck | TimeSyncResponse;

// ---------------------------------------------------------------------------
// Session Archive & REST API Types
// ---------------------------------------------------------------------------

export interface SessionSummary {
  session_id: string;
  start_time: number;
  participants: (string | { id: string; name: string })[];
  caption_count?: number;
  duration_sec?: number;
}

export interface SessionDetail {
  session_id: string;
  start_time: number;
  participants: { id: string; name: string; connection_state?: string }[];
  timeline: CaptionEvent[];
}

export interface AIAssistRequest {
  session_id: string;
  action?: "summarize" | "translate" | "query";
  query?: string;
  target_lang?: string;
  transcript_text?: string;
}

export interface AIAssistResponse {
  session_id?: string;
  result: string;
  action?: string;
}

export interface SpeakerAirtime {
  speakerId: string;
  speakerName: string;
  wordCount: number;
  charCount: number;
  finalSegmentCount: number;
  percentage: number;
  lastTimestamp?: number;
}

// ---------------------------------------------------------------------------
// Binary Audio Frame constants
// ---------------------------------------------------------------------------

export const AUDIO_MAGIC_0 = 0xAA;
export const AUDIO_MAGIC_1 = 0xBB;
export const AUDIO_HEADER_SIZE = 16;

/**
 * Build a 16-byte binary header for an audio frame.
 * Layout (big-endian):
 *   [0:1]  0xAA 0xBB
 *   [2:3]  participantIdHash (UInt16)
 *   [4:7]  seqNum (UInt32)
 *   [8:15] captureTs (BigUInt64)
 */
export function buildAudioHeader(
  participantIdHash: number,
  seqNum: number,
  captureTs: bigint,
): ArrayBuffer {
  const buf = new ArrayBuffer(AUDIO_HEADER_SIZE);
  const view = new DataView(buf);

  // Magic bytes
  view.setUint8(0, AUDIO_MAGIC_0);
  view.setUint8(1, AUDIO_MAGIC_1);

  // Participant ID hash — UInt16 big-endian
  view.setUint16(2, participantIdHash, false);

  // Sequence number — UInt32 big-endian
  view.setUint32(4, seqNum, false);

  // Capture timestamp — UInt64 big-endian
  view.setBigUint64(8, captureTs, false);

  return buf;
}

/**
 * Simple hash of a participant ID string to a UInt16.
 */
export function hashParticipantId(id: string): number {
  let hash = 0;
  for (let i = 0; i < id.length; i++) {
    hash = ((hash << 5) - hash + id.charCodeAt(i)) | 0;
  }
  return Math.abs(hash) & 0xffff;
}
