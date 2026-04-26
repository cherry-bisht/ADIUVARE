import asyncio
import json

from adiuvare.core.models import AdiuvareEvent
from adiuvare.state.event_stream import UnixSocketEventStream


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
