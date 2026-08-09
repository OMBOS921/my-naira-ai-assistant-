"""
Local Mesh Network for Multi-Device synchronization.

Uses UDP broadcast to discover other Naira-OS instances on the local network,
allowing seamless state sharing without external cloud servers.
"""

from __future__ import annotations

import asyncio
import json
import logging
import socket
import time
from dataclasses import dataclass
from typing import Any, Callable, Awaitable

_LOG = logging.getLogger("naira.mesh")

MESH_PORT = 49152  # Custom ephemeral port for Naira mesh
MAGIC_WORD = b"NAIRA_MESH_DISCOVERY"


@dataclass
class MeshNode:
    """Represents a discovered device on the mesh."""
    ip: str
    hostname: str
    last_seen: float
    device_type: str = "desktop"


class LocalMeshNetwork:
    """Manages UDP discovery and peer tracking."""

    def __init__(self, device_name: str = "Naira-Core") -> None:
        self.device_name = device_name
        self.peers: dict[str, MeshNode] = {}
        self._running = False
        self._broadcast_task: asyncio.Task[None] | None = None
        self._listen_task: asyncio.Task[None] | None = None
        self._on_peer_discovered: Callable[[MeshNode], Awaitable[None]] | None = None

        self._udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self._udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._udp_socket.setblocking(False)

    async def start(self) -> None:
        """Start the mesh networking discovery."""
        if self._running:
            return
        
        self._running = True
        
        try:
            self._udp_socket.bind(('', MESH_PORT))
        except Exception as exc:
            _LOG.warning("[MESH] Could not bind to port %d: %s", MESH_PORT, exc)
            return

        self._broadcast_task = asyncio.create_task(self._broadcast_loop())
        self._listen_task = asyncio.create_task(self._listen_loop())
        _LOG.info("[MESH] Local mesh network started on port %d", MESH_PORT)

    async def stop(self) -> None:
        """Stop the mesh network."""
        self._running = False
        if self._broadcast_task:
            self._broadcast_task.cancel()
        if self._listen_task:
            self._listen_task.cancel()
            
        try:
            self._udp_socket.close()
        except Exception:
            pass
            
        _LOG.info("[MESH] Local mesh network stopped.")

    def set_peer_callback(self, callback: Callable[[MeshNode], Awaitable[None]]) -> None:
        """Register a callback for when new peers are found."""
        self._on_peer_discovered = callback

    async def _broadcast_loop(self) -> None:
        """Periodically broadcast presence to the local network."""
        payload = json.dumps({
            "hostname": self.device_name,
            "device_type": "desktop",
            "version": "1.0",
        }).encode("utf-8")
        
        message = MAGIC_WORD + b"|" + payload

        while self._running:
            try:
                # 255.255.255.255 is local broadcast
                self._udp_socket.sendto(message, ('255.255.255.255', MESH_PORT))
            except Exception as exc:
                _LOG.debug("[MESH] Broadcast error: %s", exc)
                
            await asyncio.sleep(5.0)  # Broadcast every 5 seconds

    async def _listen_loop(self) -> None:
        """Listen for UDP broadcasts from other devices."""
        loop = asyncio.get_running_loop()
        
        while self._running:
            try:
                # Wait for data to become available
                data, addr = await loop.sock_recvfrom(self._udp_socket, 1024)
                
                if data.startswith(MAGIC_WORD):
                    # We found a Naira broadcast!
                    try:
                        payload = json.loads(data.split(b"|", 1)[1].decode("utf-8"))
                        ip = addr[0]
                        
                        # Ignore self (usually)
                        if payload.get("hostname") == self.device_name:
                            continue
                            
                        is_new = ip not in self.peers
                        
                        node = MeshNode(
                            ip=ip,
                            hostname=payload.get("hostname", "Unknown Device"),
                            last_seen=time.time(),
                            device_type=payload.get("device_type", "unknown")
                        )
                        
                        self.peers[ip] = node
                        
                        if is_new:
                            _LOG.info("[MESH] Discovered new peer: %s (%s)", node.hostname, node.ip)
                            if self._on_peer_discovered:
                                await self._on_peer_discovered(node)
                                
                    except (json.JSONDecodeError, IndexError):
                        pass
                        
            except asyncio.CancelledError:
                break
            except Exception as exc:
                _LOG.debug("[MESH] Listen error: %s", exc)
                await asyncio.sleep(1.0)
