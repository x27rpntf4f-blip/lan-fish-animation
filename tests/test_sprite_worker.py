from __future__ import annotations

import threading
from pathlib import Path

import message
from fish_demo import network_handlers


class RecordingNet:
    def __init__(self) -> None:
        self.sent: list[tuple[str, int, bytes]] = []

    def send(self, ip: str, port: int, packet: bytes) -> None:
        self.sent.append((ip, port, packet))


def _sprite_root(tmp_path: Path, *names: str) -> Path:
    root = tmp_path / "sprites"
    for name in names:
        directory = root / name
        directory.mkdir(parents=True)
        (directory / "Fish-1.png").write_bytes(name.encode())
    return root


def test_worker_performs_enumeration_and_read_off_request_thread(
    tmp_path: Path,
    monkeypatch,
) -> None:
    root = _sprite_root(tmp_path, "Purple")
    net = RecordingNet()
    caller_ident = threading.get_ident()
    read_idents: list[int] = []
    sent = threading.Event()
    original_read = network_handlers.read_regular_sprite_file

    def observed_read(*args, **kwargs):
        read_idents.append(threading.get_ident())
        return original_read(*args, **kwargs)

    def observed_send(ip: str, port: int, packet: bytes) -> None:
        net.sent.append((ip, port, packet))
        sent.set()

    monkeypatch.setattr(network_handlers, "read_regular_sprite_file", observed_read)
    net.send = observed_send
    worker = network_handlers.SpriteSendWorker(root, net, max_pending=2)
    try:
        assert worker.submit("192.0.2.10", 6200, 1, "Purple") is True
        assert sent.wait(timeout=1)
    finally:
        worker.stop()

    assert read_idents
    assert set(read_idents) == {worker.thread.ident}
    assert caller_ident not in read_idents


def test_worker_coalesces_duplicates_and_rejects_bounded_overload(
    tmp_path: Path,
    monkeypatch,
) -> None:
    root = _sprite_root(tmp_path, "Purple", "Blue", "Gold")
    net = RecordingNet()
    read_started = threading.Event()
    release_read = threading.Event()
    original_read = network_handlers.read_regular_sprite_file

    def blocking_read(*args, **kwargs):
        read_started.set()
        release_read.wait(timeout=2)
        return original_read(*args, **kwargs)

    monkeypatch.setattr(network_handlers, "read_regular_sprite_file", blocking_read)
    worker = network_handlers.SpriteSendWorker(root, net, max_pending=1)
    try:
        assert worker.submit("192.0.2.10", 6200, 1, "Purple") is True
        assert read_started.wait(timeout=1)
        assert worker.submit("192.0.2.10", 6200, 1, "Blue") is True
        assert worker.submit("192.0.2.10", 6200, 1, "Blue") is True
        assert worker.submit("192.0.2.10", 6200, 1, "Gold") is False
    finally:
        release_read.set()
        worker.stop()


def test_worker_stop_joins_before_later_chunks_can_send(
    tmp_path: Path,
    monkeypatch,
) -> None:
    root = _sprite_root(tmp_path, "Purple")
    first_send_started = threading.Event()
    release_send = threading.Event()
    sent: list[bytes] = []

    class BlockingNet:
        def send(self, _ip: str, _port: int, packet: bytes) -> None:
            sent.append(packet)
            first_send_started.set()
            release_send.wait(timeout=2)

    monkeypatch.setattr(
        network_handlers,
        "read_regular_sprite_file",
        lambda *_args, **_kwargs: b"x" * (network_handlers.CHUNK_SIZE + 1),
    )
    worker = network_handlers.SpriteSendWorker(root, BlockingNet(), max_pending=1)
    assert worker.submit("192.0.2.10", 6200, 1, "Purple") is True
    assert first_send_started.wait(timeout=1)

    stopper = threading.Thread(target=worker.stop)
    stopper.start()
    release_send.set()
    stopper.join(timeout=1)

    assert not stopper.is_alive()
    assert not worker.thread.is_alive()
    assert len(sent) == 1


def test_network_handler_only_submits_sprite_request_to_owned_worker() -> None:
    packet = message.pack_sprite_request(1, "Purple")
    submitted: list[tuple[str, int, int, str]] = []

    class SpriteManager:
        SPRITE_DIR = "must-not-be-read-by-handler"

        def get_types(self) -> list[str]:
            return ["Purple"]

    class Sender:
        def submit(self, ip: str, port: int, sender_id: int, name: str) -> bool:
            submitted.append((ip, port, sender_id, name))
            return True

    registry = type("Registry", (), {"my_id": 7})()
    network_handlers.handle_network_message(
        packet,
        ("192.0.2.10", 6200),
        object(),
        registry,
        [],
        800,
        600,
        SpriteManager(),
        object(),
        sprite_sender=Sender(),
    )

    assert submitted == [("192.0.2.10", 6200, 7, "Purple")]
