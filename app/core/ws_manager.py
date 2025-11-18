from typing import Dict, List

from fastapi import WebSocket
from starlette.websockets import WebSocketState


class WSConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, room_id: str):
        """Thêm WebSocket vào room"""
        self.active_connections.setdefault(room_id, []).append(websocket)
        print(
            f"🟢 Client joined {room_id} — total: {len(self.active_connections[room_id])}"
        )

    def disconnect(self, websocket: WebSocket, room_id: str):
        """Ngắt kết nối WebSocket khỏi room"""
        if room_id in self.active_connections:
            try:
                self.active_connections[room_id].remove(websocket)
                if not self.active_connections[room_id]:
                    del self.active_connections[room_id]
            except ValueError:
                pass
        print(f"🔴 Client left {room_id}")

    async def broadcast(self, room_id: str, message: dict):
        """Phát message cho tất cả client trong room"""
        clients = self.active_connections.get(room_id, [])
        print(f"📢 Broadcasting to {room_id} — {len(clients)} client(s)")
        for ws in list(clients):
            try:
                if ws.client_state == WebSocketState.CONNECTED:
                    await ws.send_json(message)
                else:
                    self.disconnect(ws, room_id)
            except Exception as e:
                print(f"⚠️ WS send failed ({room_id}): {e}")
                self.disconnect(ws, room_id)


# ✅ Chỉ tạo duy nhất 1 instance (singleton)
ws_manager = WSConnectionManager()
