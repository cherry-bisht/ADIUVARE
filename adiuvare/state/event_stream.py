import asyncio
import json
import os
import sys
from collections import deque
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any


class UnixSocketEventStream:
    def __init__(
        self,
        name: str = "adiuvare",
        *,
        pid: int | None = None,
        sock_path: str | Path | None = None,
    ) -> None:
        self._kind = "unix" if hasattr(asyncio, "start_unix_server") else "tcp"
        if sock_path is None:
            base = Path(os.getenv("TEMP", "/tmp"))
            tail = f"{name}.sock" if pid is None else f"{name}-{pid}.sock"
            self.path = str(base / tail)
        else:
            self.path = str(sock_path)
        self._recent = deque(maxlen=100)
        self._replay = deque(maxlen=100)
        self._clients: list[asyncio.StreamWriter] = []
        self._server = None
        self._cmd = None
        self._host = "127.0.0.1"
        self._port = 0

    async def start(self) -> None:
        if self._server is not None:
            return

        path = Path(self.path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            path.unlink()

        if self._kind == "unix":
            self._server = await asyncio.start_unix_server(self._on_connect, self.path)
            return

        self._server = await asyncio.start_server(self._on_connect, self._host, 0)
        sock = self._server.sockets[0]
        self._port = int(sock.getsockname()[1])
        path.write_text(
            json.dumps({"mode": "tcp", "host": self._host, "port": self._port}),
            encoding="utf-8",
        )

    async def emit(self, event) -> None:
        self._recent.append(event)
        payload = self._payload(event)
        self._replay.append(payload)

        if not self._clients:
            return

        dead = []
        for writer in list(self._clients):
            try:
                writer.write(payload)
                await writer.drain()
            except (BrokenPipeError, ConnectionResetError):
                dead.append(writer)

        for writer in dead:
            if writer in self._clients:
                self._clients.remove(writer)

    def recent(self) -> list:
        return list(self._recent)

    def set_command_handler(self, handler) -> None:
        self._cmd = handler

    async def command(self, name: str, args: dict | None = None) -> dict:
        if self._cmd is None:
            raise RuntimeError("stream_command_unbound")
        return await self._cmd(name, args or {})

    async def connect(self):
        if self._kind == "unix":
            return await asyncio.open_unix_connection(self.path)
        return await asyncio.open_connection(self._host, self._port)

    async def stop(self) -> None:
        for writer in list(self._clients):
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass
        self._clients.clear()

        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

        path = Path(self.path)
        if path.exists():
            path.unlink()

    async def _on_connect(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        self._clients.append(writer)
        try:
            for payload in self._replay:
                writer.write(payload)
            await writer.drain()
            await reader.read(1)
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            if writer in self._clients:
                self._clients.remove(writer)
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass

    def _payload(self, event: Any) -> bytes:
        if is_dataclass(event):
            data = asdict(event)
        elif isinstance(event, dict):
            data = event
        else:
            data = {"value": str(event)}
        return (json.dumps(data) + "\n").encode("utf-8")


class RedisEventStream:
    def __init__(self, project: str, redis_url: str) -> None:
        self._channel = f"adiuvare:events:{project}"
        self._url = redis_url
        self._client = None
        self._replay = deque(maxlen=100)

    async def start(self) -> None:
        mod = sys.modules.get("redis.asyncio")
        if mod is None:
            import redis.asyncio as mod

        self._client = mod.from_url(self._url)

    async def emit(self, event) -> None:
        data = asdict(event) if is_dataclass(event) else event
        payload = json.dumps(data)
        self._replay.append(payload)

        if self._client is None:
            return

        await self._client.publish(self._channel, payload)
        key = f"{self._channel}:replay"
        await self._client.lpush(key, payload)
        await self._client.ltrim(key, 0, 99)

    async def stop(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None
