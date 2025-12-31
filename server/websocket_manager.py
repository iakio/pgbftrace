import struct
from typing import List
from fastapi import WebSocket
from models import TraceEvent


class ConnectionManager:
    """Manages WebSocket connections and broadcasting"""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        """Accept and register new WebSocket connection"""
        await websocket.accept()
        self.active_connections.append(websocket)
        print(f"Client connected. Total clients: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        """Remove WebSocket connection from active list"""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            print(f"Client disconnected. Total clients: {len(self.active_connections)}")

    async def disconnect_all(self):
        """Safely close all WebSocket connections"""
        connections_to_close = list(self.active_connections)
        for connection in connections_to_close:
            try:
                await connection.close(code=1001, reason="Server shutting down")
            except Exception as e:
                print(f"Error closing WebSocket connection: {e}")
        self.active_connections.clear()
        print("All WebSocket connections closed.")

    async def broadcast_bytes(self, message: bytes):
        """Broadcast binary message to all active connections"""
        if not self.active_connections:
            return
            
        disconnected_connections = []
        for connection in self.active_connections:
            try:
                await connection.send_bytes(message)
            except Exception as e:
                print(f"Failed to send to a client, marking for removal: {e}")
                disconnected_connections.append(connection)
        
        # Clean up failed connections
        for connection in disconnected_connections:
            self.disconnect(connection)

    async def broadcast_trace_event(self, trace_event: TraceEvent):
        """Broadcast trace event as binary data"""
        packed_data = struct.pack('!II', trace_event.relfilenode, trace_event.block)
        await self.broadcast_bytes(packed_data)