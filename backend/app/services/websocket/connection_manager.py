"""
WebSocket connection management
"""

import asyncio
import logging
from typing import Dict, Set, Optional, List, Any
from datetime import datetime
import uuid
from fastapi import WebSocket, WebSocketDisconnect

from .message_protocol import WebSocketMessage, MessageType, create_error_message, create_ping_message

logger = logging.getLogger(__name__)


class Connection:
    """Represents a WebSocket connection"""
    
    def __init__(self, websocket: WebSocket, connection_id: str, client_info: Dict[str, Any] = None):
        self.websocket = websocket
        self.connection_id = connection_id
        self.session_id = str(uuid.uuid4())
        self.connected_at = datetime.now()
        self.last_ping = datetime.now()
        self.client_info = client_info or {}
        self.active = True
        self.subscriptions: Set[str] = set()
    
    async def send_message(self, message: WebSocketMessage) -> bool:
        """Send message to this connection"""
        try:
            if not self.active:
                return False
            
            # Add session ID if not present
            if not message.session_id:
                message.session_id = self.session_id
            
            await self.websocket.send_text(message.to_json())
            return True
            
        except Exception as e:
            logger.error(f"Failed to send message to connection {self.connection_id}: {e}")
            self.active = False
            return False
    
    async def send_json(self, data: dict) -> bool:
        """Send raw JSON data"""
        try:
            if not self.active:
                return False
            
            await self.websocket.send_json(data)
            return True
            
        except Exception as e:
            logger.error(f"Failed to send JSON to connection {self.connection_id}: {e}")
            self.active = False
            return False
    
    def subscribe(self, channel: str):
        """Subscribe to a channel"""
        self.subscriptions.add(channel)
    
    def unsubscribe(self, channel: str):
        """Unsubscribe from a channel"""
        self.subscriptions.discard(channel)
    
    def is_subscribed(self, channel: str) -> bool:
        """Check if subscribed to a channel"""
        return channel in self.subscriptions


class ConnectionManager:
    """Manages WebSocket connections"""
    
    def __init__(self):
        self.active_connections: Dict[str, Connection] = {}
        self.ping_interval = 30  # seconds
        self.ping_timeout = 10   # seconds
        self._ping_task = None
        self._lock = asyncio.Lock()
    
    async def connect(self, websocket: WebSocket, client_info: Dict[str, Any] = None) -> Connection:
        """Accept and register a new connection"""
        await websocket.accept()
        
        connection_id = str(uuid.uuid4())
        connection = Connection(websocket, connection_id, client_info)
        
        async with self._lock:
            self.active_connections[connection_id] = connection
        
        logger.info(f"WebSocket connection established: {connection_id}")
        
        # Start ping task if not running
        if not self._ping_task or self._ping_task.done():
            self._ping_task = asyncio.create_task(self._ping_loop())
        
        return connection
    
    async def disconnect(self, connection_id: str):
        """Disconnect and remove a connection"""
        async with self._lock:
            connection = self.active_connections.pop(connection_id, None)
        
        if connection:
            connection.active = False
            try:
                await connection.websocket.close()
            except Exception:
                pass
            
            logger.info(f"WebSocket connection closed: {connection_id}")
    
    async def send_to_connection(self, connection_id: str, message: WebSocketMessage) -> bool:
        """Send message to specific connection"""
        connection = self.active_connections.get(connection_id)
        if connection:
            return await connection.send_message(message)
        return False
    
    async def broadcast(self, message: WebSocketMessage, exclude: Optional[Set[str]] = None):
        """Broadcast message to all connections"""
        exclude = exclude or set()
        
        # Create tasks for parallel sending
        tasks = []
        for conn_id, connection in list(self.active_connections.items()):
            if conn_id not in exclude and connection.active:
                tasks.append(connection.send_message(message))
        
        # Execute all sends in parallel
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Clean up failed connections
            failed_connections = []
            for i, (conn_id, connection) in enumerate(list(self.active_connections.items())):
                if isinstance(results[i], Exception) or not results[i]:
                    failed_connections.append(conn_id)
            
            for conn_id in failed_connections:
                await self.disconnect(conn_id)
    
    async def broadcast_to_channel(self, channel: str, message: WebSocketMessage, exclude: Optional[Set[str]] = None):
        """Broadcast message to all connections subscribed to a channel"""
        exclude = exclude or set()
        
        tasks = []
        for conn_id, connection in list(self.active_connections.items()):
            if (conn_id not in exclude and 
                connection.active and 
                connection.is_subscribed(channel)):
                tasks.append(connection.send_message(message))
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    async def send_to_session(self, session_id: str, message: WebSocketMessage) -> bool:
        """Send message to connection by session ID"""
        for connection in self.active_connections.values():
            if connection.session_id == session_id:
                return await connection.send_message(message)
        return False
    
    def get_connection(self, connection_id: str) -> Optional[Connection]:
        """Get connection by ID"""
        return self.active_connections.get(connection_id)
    
    def get_connection_by_session(self, session_id: str) -> Optional[Connection]:
        """Get connection by session ID"""
        for connection in self.active_connections.values():
            if connection.session_id == session_id:
                return connection
        return None
    
    def get_all_connections(self) -> List[Connection]:
        """Get all active connections"""
        return list(self.active_connections.values())
    
    def get_connection_count(self) -> int:
        """Get number of active connections"""
        return len(self.active_connections)
    
    def get_channel_subscribers(self, channel: str) -> List[Connection]:
        """Get all connections subscribed to a channel"""
        subscribers = []
        for connection in self.active_connections.values():
            if connection.is_subscribed(channel):
                subscribers.append(connection)
        return subscribers
    
    async def _ping_loop(self):
        """Background task to ping connections"""
        while self.active_connections:
            try:
                await asyncio.sleep(self.ping_interval)
                
                # Send ping to all connections
                ping_message = create_ping_message()
                dead_connections = []
                
                for conn_id, connection in list(self.active_connections.items()):
                    if connection.active:
                        success = await connection.send_message(ping_message)
                        if not success:
                            dead_connections.append(conn_id)
                        else:
                            connection.last_ping = datetime.now()
                    else:
                        dead_connections.append(conn_id)
                
                # Clean up dead connections
                for conn_id in dead_connections:
                    await self.disconnect(conn_id)
                
            except Exception as e:
                logger.error(f"Error in ping loop: {e}")
    
    async def cleanup(self):
        """Clean up all connections"""
        # Cancel ping task
        if self._ping_task and not self._ping_task.done():
            self._ping_task.cancel()
            try:
                await self._ping_task
            except asyncio.CancelledError:
                pass
        
        # Close all connections
        connection_ids = list(self.active_connections.keys())
        for conn_id in connection_ids:
            await self.disconnect(conn_id)
        
        logger.info("ConnectionManager cleaned up")