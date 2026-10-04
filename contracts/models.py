"""
Roundtable Protocol Models (v1.0)

Typed Pydantic models derived from the authoritative contracts in
docs/plan/02_contracts.md. DO NOT modify the contracts; update models
here only if the contracts change.

Design decisions (see NOTES.md):
  - CaptionEvent uses the FULL schema from 02_contracts.md (with
    speaker_name, start_ts, end_ts, revision) rather than the
    abbreviated version in the prompt §3.
  - JoinAck.history is typed as List[CaptionEvent] (caption history).
  - Binary audio frame uses big-endian (network byte order).
  - Participant.connection_state uses a str enum: ACTIVE | DISCONNECTED.
"""

from __future__ import annotations

import struct
from enum import Enum
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Client -> Server messages
# ---------------------------------------------------------------------------

class JoinRequest(BaseModel):
    """Client requests to join a session."""
    type: Literal["JOIN"] = "JOIN"
    session_id: str
    participant_name: str
    participant_id: Optional[str] = None



class TimeSyncRequest(BaseModel):
    """Client sends its transmit timestamp for clock sync."""
    type: Literal["SYNC"] = "SYNC"
    client_tx_ts: int  # milliseconds since epoch


# ---------------------------------------------------------------------------
# Server -> Client messages
# ---------------------------------------------------------------------------

class CaptionEvent(BaseModel):
    """A single caption segment (partial or final)."""
    type: Literal["CAPTION"] = "CAPTION"
    segment_id: str
    speaker_id: str
    speaker_name: str = ""
    start_ts: int = 0        # session-relative ms
    end_ts: int = 0          # session-relative ms
    text: str
    is_final: bool = False
    revision: int = 1


class JoinAck(BaseModel):
    """Server acknowledges a JOIN and assigns a participant ID."""
    type: Literal["JOIN_ACK"] = "JOIN_ACK"
    participant_id: str
    history: List[CaptionEvent] = Field(default_factory=list)


class TimeSyncResponse(BaseModel):
    """Server responds with its own timestamps for clock offset calc."""
    type: Literal["SYNC_ACK"] = "SYNC_ACK"
    client_tx_ts: int
    server_rx_ts: int
    server_tx_ts: int


# ---------------------------------------------------------------------------
# Session & Participant models
# ---------------------------------------------------------------------------

class ConnectionState(str, Enum):
    ACTIVE = "ACTIVE"
    DISCONNECTED = "DISCONNECTED"


class Participant(BaseModel):
    """A participant in a Roundtable session."""
    id: str
    name: str
    connection_state: ConnectionState = ConnectionState.ACTIVE
    clock_offset_ms: int = 0


class Session(BaseModel):
    """A Roundtable session (room)."""
    session_id: str
    participants: List[Participant] = Field(default_factory=list)
    timeline: List[CaptionEvent] = Field(default_factory=list)
    start_time: int = 0  # epoch ms


# ---------------------------------------------------------------------------
# Binary Audio Frame helpers
# ---------------------------------------------------------------------------

AUDIO_MAGIC = b"\xAA\xBB"
AUDIO_HEADER_SIZE = 16  # bytes


class AudioFrameHeader(BaseModel):
    """Parsed 16-byte audio frame header."""
    participant_id_hash: int  # UInt16
    seq_num: int              # UInt32
    capture_ts: int           # UInt64 (ms since epoch)

    def to_bytes(self) -> bytes:
        """Serialize header to 16 bytes (big-endian)."""
        return (
            AUDIO_MAGIC
            + struct.pack(
                ">HIQ",
                self.participant_id_hash,
                self.seq_num,
                self.capture_ts,
            )
        )

    @classmethod
    def from_bytes(cls, data: bytes) -> "AudioFrameHeader":
        """Parse 16-byte header. Raises ValueError on bad magic/length."""
        if len(data) < AUDIO_HEADER_SIZE:
            raise ValueError(
                f"Audio frame too short: {len(data)} < {AUDIO_HEADER_SIZE}"
            )
        if data[0:2] != AUDIO_MAGIC:
            raise ValueError(
                f"Bad magic bytes: {data[0:2]!r}, expected {AUDIO_MAGIC!r}"
            )
        pid_hash, seq_num, capture_ts = struct.unpack(">HIQ", data[2:16])
        return cls(
            participant_id_hash=pid_hash,
            seq_num=seq_num,
            capture_ts=capture_ts,
        )


# ---------------------------------------------------------------------------
# Message dispatcher helper
# ---------------------------------------------------------------------------

MESSAGE_TYPES = {
    "JOIN": JoinRequest,
    "SYNC": TimeSyncRequest,
    "JOIN_ACK": JoinAck,
    "SYNC_ACK": TimeSyncResponse,
    "CAPTION": CaptionEvent,
}


def parse_message(raw: dict) -> BaseModel:
    """Parse a JSON dict into the appropriate Pydantic model.

    Raises KeyError if 'type' is missing or unknown.
    """
    msg_type = raw["type"]
    model_cls = MESSAGE_TYPES[msg_type]
    return model_cls(**raw)
