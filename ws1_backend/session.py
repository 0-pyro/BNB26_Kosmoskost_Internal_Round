"""
Session and Room Management for Roundtable Backend.

Maintains active ROOMS, connected WebSockets, participant state,
caption history buffering, and 60-second disconnect grace periods.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

from starlette.websockets import WebSocket

# Ensure project root is on sys.path for contracts import
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from contracts.models import (
    CaptionEvent,
    ConnectionState,
    Participant,
    Session,
)

logger = logging.getLogger("ws1_backend.session")


class Connection:
    """Wrapper around a Starlette/FastAPI WebSocket with concurrency lock."""

    def __init__(self, websocket: WebSocket):
        self.websocket = websocket
        self._lock = asyncio.Lock()

    async def send_text(self, text: str) -> None:
        """Send text frame with write lock to prevent concurrent write collisions."""
        async with self._lock:
            await self.websocket.send_text(text)

    async def send_bytes(self, data: bytes) -> None:
        """Send binary frame with write lock."""
        async with self._lock:
            await self.websocket.send_bytes(data)

    async def send_json(self, data: Any) -> None:
        """Serialize data (Pydantic model, dict, or str) and send as text frame."""
        if hasattr(data, "model_dump_json"):
            text = data.model_dump_json()
        elif isinstance(data, dict):
            text = json.dumps(data)
        elif isinstance(data, str):
            text = data
        else:
            text = str(data)
        await self.send_text(text)


class Room:
    """A Roundtable session room holding participants, connections, and caption timeline."""

    def __init__(self, session_id: str, disconnect_timeout: float = 60.0):
        self.session_id: str = session_id
        self.disconnect_timeout: float = disconnect_timeout
        self.participants: Dict[str, Participant] = {}
        self.connections: Dict[str, Connection] = {}
        self.timeline: List[CaptionEvent] = []
        self.cleanup_tasks: Dict[str, asyncio.Task] = {}
        self.copilot_tasks: List[asyncio.Task] = []
        self.lock = asyncio.Lock()
        self.created_at: int = int(time.time() * 1000)
        self.active_speaker_id: Optional[str] = None
        self.active_speaker_rms: float = 0.0
        self.active_speaker_ts: float = 0.0

    def register_audio_energy(self, participant_id: str, rms: float) -> bool:
        """
        Multi-device room-level acoustic arbitration.
        Returns True if this participant's frame should be processed for speech transcription,
        or False if it is likely acoustic echo/crosstalk from another louder active participant.
        """
        now = time.time()
        # If quiet/ambient, allow frame to pass through (for silence tracking)
        if rms < 0.018:
            return True

        # If no active speaker or last speech was >1.5s ago, this participant takes the floor
        if self.active_speaker_id is None or (now - self.active_speaker_ts > 1.5):
            self.active_speaker_id = participant_id
            self.active_speaker_rms = rms
            self.active_speaker_ts = now
            return True

        # If this is the current active speaker, update their energy and timestamp
        if self.active_speaker_id == participant_id:
            self.active_speaker_rms = max(self.active_speaker_rms * 0.9, rms)
            self.active_speaker_ts = now
            return True

        # Another participant is speaking at the same time:
        # If this participant is significantly louder, hand off the floor
        if rms > self.active_speaker_rms * 1.3:
            self.active_speaker_id = participant_id
            self.active_speaker_rms = rms
            self.active_speaker_ts = now
            return True

        # If this participant's RMS is significantly weaker (<60% of active speaker),
        # it is room reverberation / mic spillover from the active speaker. Suppress!
        if rms < self.active_speaker_rms * 0.60:
            return False

        # Otherwise (comparable volume, natural overlap / barge-in), allow
        return True

    async def join(
        self,
        participant_name: str,
        connection: Connection,
        requested_pid: Optional[str] = None,
    ) -> Tuple[Participant, List[CaptionEvent]]:
        """
        Handle a participant joining the room.

        Supports reconnection if the participant disconnected within the grace period.
        Returns the assigned/reconnected Participant and the current caption history.
        """
        async with self.lock:
            # 1. Check for reconnect by explicit requested_pid
            if requested_pid and requested_pid in self.participants:
                existing = self.participants[requested_pid]
                logger.info(
                    "Participant %s (%s) reconnected by pid in room %s",
                    existing.name,
                    existing.id,
                    self.session_id,
                )
                self._cancel_cleanup(existing.id)
                old_conn = self.connections.get(existing.id)
                if old_conn and old_conn != connection:
                    try:
                        asyncio.create_task(old_conn.close())
                    except Exception:
                        pass
                existing.connection_state = ConnectionState.ACTIVE
                self.connections[existing.id] = connection
                return existing, list(self.timeline)

            # 2. Check for reconnect by participant_name if disconnected
            for pid, p in self.participants.items():
                if p.name == participant_name and p.connection_state == ConnectionState.DISCONNECTED:
                    logger.info(
                        "Participant %s (%s) reconnected by name in room %s",
                        p.name,
                        p.id,
                        self.session_id,
                    )
                    self._cancel_cleanup(p.id)
                    p.connection_state = ConnectionState.ACTIVE
                    self.connections[p.id] = connection
                    return p, list(self.timeline)

            # 3. New participant (or another active participant with same name)
            assigned_name = participant_name
            active_names = [
                p.name
                for p in self.participants.values()
                if p.connection_state == ConnectionState.ACTIVE
            ]
            if participant_name in active_names:
                # Disambiguate duplicate names: e.g. "Alice (1)"
                count = sum(1 for n in active_names if n.startswith(participant_name))
                assigned_name = f"{participant_name} ({count})"

            new_pid = requested_pid if requested_pid and requested_pid not in self.participants else f"p_{uuid.uuid4().hex[:8]}"
            participant = Participant(
                id=new_pid,
                name=assigned_name,
                connection_state=ConnectionState.ACTIVE,
                clock_offset_ms=0,
            )
            self.participants[new_pid] = participant
            self.connections[new_pid] = connection
            logger.info(
                "Participant %s assigned id %s in room %s",
                assigned_name,
                new_pid,
                self.session_id,
            )
            return participant, list(self.timeline)

    def _cancel_cleanup(self, participant_id: str) -> None:
        """Cancel pending cleanup timer task for a participant."""
        task = self.cleanup_tasks.pop(participant_id, None)
        if task and not task.done():
            task.cancel()

    async def disconnect(self, participant_id: str) -> None:
        """
        Mark participant as DISCONNECTED (inactive) and keep them in the room for
        disconnect_timeout (default 60s) for potential reconnects.
        """
        async with self.lock:
            if participant_id in self.participants:
                participant = self.participants[participant_id]
                participant.connection_state = ConnectionState.DISCONNECTED
                self.connections.pop(participant_id, None)
                self._cancel_cleanup(participant_id)

                logger.info(
                    "Participant %s (%s) marked DISCONNECTED in room %s (grace period: %.1fs)",
                    participant.name,
                    participant_id,
                    self.session_id,
                    self.disconnect_timeout,
                )

                # Schedule cleanup after disconnect_timeout
                task = asyncio.create_task(
                    self._cleanup_after_grace_period(participant_id, self.disconnect_timeout)
                )
                self.cleanup_tasks[participant_id] = task

    async def _cleanup_after_grace_period(self, participant_id: str, timeout: float) -> None:
        """Wait for timeout seconds, then remove participant if still disconnected."""
        try:
            await asyncio.sleep(timeout)
            async with self.lock:
                participant = self.participants.get(participant_id)
                if participant and participant.connection_state == ConnectionState.DISCONNECTED:
                    logger.info(
                        "Grace period expired for participant %s (%s) in room %s; removing.",
                        participant.name,
                        participant_id,
                        self.session_id,
                    )
                    self.participants.pop(participant_id, None)
                    self.cleanup_tasks.pop(participant_id, None)
                    # Clean up empty room if no participants remain
                    if not self.participants:
                        await session_manager.remove_room_if_empty(self.session_id)
        except asyncio.CancelledError:
            # Participant reconnected; cleanup cancelled
            pass

    async def close(self) -> None:
        """Close the room, persist transcript to storage, and cancel pending tasks."""
        async with self.lock:
            if self.timeline:
                try:
                    from ws1_backend.storage import session_storage
                    session_storage.save_session(
                        session_id=self.session_id,
                        transcript=list(self.timeline),
                        created_at=self.created_at,
                    )
                except Exception as exc:
                    logger.warning("Failed to persist session %s on close: %s", self.session_id, exc)
            for task in list(self.cleanup_tasks.values()):
                if not task.done():
                    task.cancel()
            self.cleanup_tasks.clear()

    async def clear(self) -> None:
        """Persist transcript to storage and clear the room timeline."""
        async with self.lock:
            if self.timeline:
                try:
                    from ws1_backend.storage import session_storage
                    session_storage.save_session(
                        session_id=self.session_id,
                        transcript=list(self.timeline),
                        created_at=self.created_at,
                    )
                except Exception as exc:
                    logger.warning("Failed to persist session %s on clear: %s", self.session_id, exc)
                self.timeline.clear()


    async def add_caption(self, caption: CaptionEvent, broadcast: bool = True) -> None:
        """Append CaptionEvent to the room history and optionally broadcast to all active clients."""
        # Check for "Hey Roundtable" wake-word interception on finalized text segments
        if caption.is_final and caption.speaker_id != "Roundtable AI":
            from ws1_backend.copilot import extract_wake_word_query
            query = extract_wake_word_query(caption.text)
            if query is not None:
                logger.info(
                    "Wake-word intercepted in room %s from %s: %r",
                    self.session_id,
                    caption.speaker_name or caption.speaker_id,
                    query,
                )
                task = asyncio.create_task(
                    self.handle_voice_copilot(query, trigger_caption=caption)
                )
                self.copilot_tasks = [t for t in self.copilot_tasks if not t.done()]
                self.copilot_tasks.append(task)
                # Do NOT broadcast this segment as a normal user caption
                return

        async with self.lock:
            self.timeline.append(caption)

        if broadcast:
            await self.broadcast(caption)

    async def handle_voice_copilot(
        self,
        query: str,
        client: Optional[Any] = None,
        model: Optional[str] = None,
        trigger_caption: Optional[CaptionEvent] = None,
    ) -> Optional[CaptionEvent]:
        """Trigger Voice Copilot handling for this room."""
        from ws1_backend.copilot import handle_voice_copilot
        return await handle_voice_copilot(
            self,
            query,
            client=client,
            model=model,
            trigger_caption=trigger_caption,
        )

    async def broadcast(
        self,
        message: Any,
        exclude_pid: Optional[str] = None,
    ) -> None:
        """Broadcast a message to all active WebSocket connections in the room concurrently."""
        async with self.lock:
            recipients = [
                (pid, conn)
                for pid, conn in self.connections.items()
                if pid != exclude_pid
            ]

        if not recipients:
            return

        async def _safe_send(pid: str, conn: Connection) -> None:
            try:
                await conn.send_json(message)
            except Exception as exc:
                logger.warning("Failed to broadcast message to %s: %s", pid, exc)

        await asyncio.gather(*[_safe_send(pid, conn) for pid, conn in recipients], return_exceptions=True)

    def get_history(self) -> List[CaptionEvent]:
        """Return the current caption history list."""
        return list(self.timeline)

    def to_session_model(self) -> Session:
        """Convert room state to the authoritative Session model."""
        return Session(
            session_id=self.session_id,
            participants=list(self.participants.values()),
            timeline=list(self.timeline),
            start_time=self.created_at,
        )


# Global active rooms dictionary
ROOMS: Dict[str, Room] = {}


class SessionManager:
    """Manages active rooms and their lifecycles."""

    def __init__(self, rooms_dict: Optional[Dict[str, Room]] = None):
        self.rooms: Dict[str, Room] = rooms_dict if rooms_dict is not None else ROOMS
        self._lock = asyncio.Lock()

    async def get_or_create_room(
        self, session_id: str, disconnect_timeout: float = 60.0
    ) -> Room:
        """Get existing room or create a new one."""
        async with self._lock:
            if session_id not in self.rooms:
                self.rooms[session_id] = Room(
                    session_id=session_id, disconnect_timeout=disconnect_timeout
                )
            return self.rooms[session_id]

    async def get_room(self, session_id: str) -> Optional[Room]:
        """Get room by session_id if it exists."""
        async with self._lock:
            return self.rooms.get(session_id)

    async def remove_room(self, session_id: str) -> Optional[Room]:
        """Remove a room by session_id and persist its transcript."""
        async with self._lock:
            room = self.rooms.pop(session_id, None)
        if room:
            await room.close()
        return room

    async def remove_room_if_empty(self, session_id: str) -> bool:
        """Remove room if it has 0 participants left and persist its transcript."""
        async with self._lock:
            room = self.rooms.get(session_id)
            if room and not room.participants:
                self.rooms.pop(session_id, None)
            else:
                room = None
        if room:
            await room.close()
            return True
        return False

    async def close_room(self, session_id: str) -> Optional[Room]:
        """Explicitly close and persist an active room."""
        return await self.remove_room(session_id)

    async def save_room(self, session_id: str) -> bool:
        """Persist an active room's transcript to storage without removing it."""
        async with self._lock:
            room = self.rooms.get(session_id)
        if room and room.timeline:
            from ws1_backend.storage import session_storage
            session_storage.save_session(
                session_id=room.session_id,
                transcript=list(room.timeline),
                created_at=room.created_at,
            )
            return True
        return False

    def reset(self) -> None:
        """Clear all active rooms, persist any transcripts, and cancel cleanup tasks."""
        for room in list(self.rooms.values()):
            for task in list(room.cleanup_tasks.values()):
                if not task.done():
                    task.cancel()
            for task in list(room.copilot_tasks):
                if not task.done():
                    task.cancel()
            if room.timeline:
                try:
                    from ws1_backend.storage import session_storage
                    session_storage.save_session(
                        session_id=room.session_id,
                        transcript=list(room.timeline),
                        created_at=room.created_at,
                    )
                except Exception as exc:
                    logger.warning("Failed to persist session %s on reset: %s", room.session_id, exc)
        self.rooms.clear()



# Default singleton instance
session_manager = SessionManager(ROOMS)
