"""WebSocket connection manager for real-time agent task updates."""
from __future__ import annotations

import json
from typing import Any, Dict, Optional

import structlog
from fastapi import WebSocket

logger = structlog.get_logger(__name__)


class ConnectionManager:
    """Manages active WebSocket connections keyed by client_id."""

    def __init__(self) -> None:
        self._connections: Dict[str, WebSocket] = {}

    async def connect(self, client_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections[client_id] = websocket
        logger.info("ws.connected", client_id=client_id, total=len(self._connections))

    def disconnect(self, client_id: str) -> None:
        self._connections.pop(client_id, None)
        logger.info("ws.disconnected", client_id=client_id, total=len(self._connections))

    async def send(self, client_id: str, data: Dict[str, Any]) -> bool:
        """Send JSON message to a specific client. Returns False if client not connected."""
        ws = self._connections.get(client_id)
        if not ws:
            return False
        try:
            await ws.send_text(json.dumps(data))
            return True
        except Exception as exc:
            logger.warning("ws.send_failed", client_id=client_id, error=str(exc))
            self.disconnect(client_id)
            return False

    async def broadcast(self, data: Dict[str, Any]) -> int:
        """Broadcast to all connected clients. Returns count sent."""
        dead: list[str] = []
        sent = 0
        for cid, ws in self._connections.items():
            try:
                await ws.send_text(json.dumps(data))
                sent += 1
            except Exception:
                dead.append(cid)
        for cid in dead:
            self.disconnect(cid)
        return sent

    async def notify_task_update(
        self,
        client_id: str,
        task_id: str,
        status: str,
        progress: int,
        result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> None:
        """Send a standardized task update event."""
        await self.send(client_id, {
            "type": "task_update",
            "task_id": task_id,
            "status": status,
            "progress": progress,
            "result": result,
            "error": error,
        })

    @property
    def connected_count(self) -> int:
        return len(self._connections)
