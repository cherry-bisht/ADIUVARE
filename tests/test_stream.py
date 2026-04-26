import asyncio
import json
import sys
import types

from adiuvare.core.models import AdiuvareEvent
from adiuvare.state.event_stream import RedisEventStream, UnixSocketEventStream


def test_stream_replays_recent_event_to_new_client(tmp_path):
    async def run():
        stream = UnixSocketEventStream(sock_path=tmp_path / "replay.sock")
        await stream.start()
        try:
            await stream.emit(
                AdiuvareEvent(
                    identity="u1",
                    endpoint="/login",
                    score=0.88,
                    verdict="block",
                    breakdown={"payload": 0.88},
                )
            )
            reader, writer = await stream.connect()
            try:
                line = await asyncio.wait_for(reader.readline(), timeout=0.5)
            finally:
                writer.close()
                await writer.wait_closed()

            data = json.loads(line.decode("utf-8"))
            assert data["identity"] == "u1"
            assert data["verdict"] == "block"
        finally:
            await stream.stop()

    asyncio.run(run())


def test_stream_broadcasts_live_event(tmp_path):
    async def run():
        stream = UnixSocketEventStream(sock_path=tmp_path / "live.sock")
        await stream.start()
        try:
            reader, writer = await stream.connect()
            try:
                await stream.emit(
                    AdiuvareEvent(
                        identity="u2",
                        endpoint="/pay",
                        score=0.42,
                        verdict="flag",
                        breakdown={"payload": 0.42},
                    )
                )
                line = await asyncio.wait_for(reader.readline(), timeout=0.5)
            finally:
                writer.close()
                await writer.wait_closed()

            data = json.loads(line.decode("utf-8"))
            assert data["endpoint"] == "/pay"
            assert data["verdict"] == "flag"
        finally:
            await stream.stop()

    asyncio.run(run())


def test_stream_stop_removes_socket_path(tmp_path):
    async def run():
        sock_path = tmp_path / "done.sock"
        stream = UnixSocketEventStream(sock_path=sock_path)
        await stream.start()
        assert sock_path.exists()
        await stream.stop()
        assert not sock_path.exists()

    asyncio.run(run())


def test_stream_command_handler_still_works(tmp_path):
    async def run():
        stream = UnixSocketEventStream(sock_path=tmp_path / "cmd.sock")

        async def fake_cmd(name: str, args: dict):
            return {"name": name, "args": args}

        stream.set_command_handler(fake_cmd)
        res = await stream.command("ping", {"ok": True})
        assert res == {"name": "ping", "args": {"ok": True}}

    asyncio.run(run())


def test_redis_stream_publishes_and_replays(monkeypatch):
    seen = {}

    class FakeClient:
        async def publish(self, channel, payload):
            seen["pub"] = (channel, json.loads(payload))

        async def lpush(self, key, payload):
            seen["lpush"] = (key, json.loads(payload))

        async def ltrim(self, key, low, high):
            seen["trim"] = (key, low, high)

        async def aclose(self):
            seen["closed"] = True

    fake_client = FakeClient()
    redis_pkg = types.ModuleType("redis")
    redis_async = types.ModuleType("redis.asyncio")

    def from_url(url):
        seen["url"] = url
        return fake_client

    redis_async.from_url = from_url
    redis_pkg.asyncio = redis_async
    monkeypatch.setitem(sys.modules, "redis", redis_pkg)
    monkeypatch.setitem(sys.modules, "redis.asyncio", redis_async)

    async def run():
        stream = RedisEventStream(project="demo", redis_url="redis://127.0.0.1:6379/0")
        await stream.start()
        await stream.emit(
            AdiuvareEvent(
                identity="u9",
                endpoint="/search",
                score=0.61,
                verdict="throttle",
                breakdown={"payload": 0.61},
            )
        )
        await stream.stop()

    asyncio.run(run())

    assert seen["url"] == "redis://127.0.0.1:6379/0"
    assert seen["pub"][0] == "adiuvare:events:demo"
    assert seen["pub"][1]["identity"] == "u9"
    assert seen["lpush"][0] == "adiuvare:events:demo:replay"
    assert seen["trim"] == ("adiuvare:events:demo:replay", 0, 99)
    assert seen["closed"] is True
