from __future__ import annotations

import queue
import threading

import pytest

import network
from network import HostRegistry, NetworkManager


class BlockingSocket:
    def __init__(self) -> None:
        self.recv_entered = threading.Event()
        self.release_recv = threading.Event()
        self.sent: list[tuple[bytes, tuple[str, int]]] = []
        self.closed = False

    def setsockopt(self, *_args: object) -> None:
        pass

    def settimeout(self, _timeout: float) -> None:
        pass

    def bind(self, _endpoint: tuple[str, int]) -> None:
        pass

    def recvfrom(self, _size: int):
        self.recv_entered.set()
        self.release_recv.wait(timeout=2)
        self.release_recv.clear()
        raise TimeoutError

    def sendto(self, data: bytes, endpoint: tuple[str, int]) -> None:
        self.sent.append((data, endpoint))

    def close(self) -> None:
        self.closed = True
        self.release_recv.set()


def _registry(monkeypatch: pytest.MonkeyPatch) -> HostRegistry:
    monkeypatch.setattr(HostRegistry, "_get_my_ip", staticmethod(lambda: "127.0.0.1"))
    registry = HostRegistry(6200)
    registry.add_or_update("one", "192.0.2.10", 6201)
    return registry


def test_async_send_uses_endpoint_snapshot_taken_before_registry_changes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sock = BlockingSocket()
    monkeypatch.setattr(network.socket, "socket", lambda *_args: sock)
    manager = NetworkManager(6200)
    registry = _registry(monkeypatch)
    manager.start_listen(queue.Queue())
    assert sock.recv_entered.wait(timeout=1)

    manager.send_heartbeat_async(b"heartbeat", registry)
    registry.remove_by_key("192.0.2.10:6201")
    registry.add_or_update("two", "192.0.2.20", 6202)
    sock.release_recv.set()

    for _ in range(100):
        if sock.sent:
            break
        threading.Event().wait(0.005)
    manager.shutdown()

    assert sock.sent == [(b"heartbeat", ("192.0.2.10", 6201))]


def test_send_known_isolates_one_endpoint_failure_and_uses_snapshot() -> None:
    manager = NetworkManager.__new__(NetworkManager)
    sent: list[tuple[str, int]] = []

    def send(ip: str, port: int, _data: bytes) -> None:
        if ip == "192.0.2.10":
            raise RuntimeError("peer disappeared")
        sent.append((ip, port))

    manager.send = send
    endpoints = (("192.0.2.10", 6201), ("192.0.2.20", 6202))

    manager.send_known(b"heartbeat", endpoints)

    assert sent == [("192.0.2.20", 6202)]


def test_registry_endpoint_snapshot_survives_concurrent_membership_changes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry = _registry(monkeypatch)
    stop = threading.Event()
    failures: list[BaseException] = []

    def mutate() -> None:
        try:
            index = 0
            while not stop.is_set():
                key = f"192.0.2.{20 + index % 10}:63{index % 10:02d}"
                ip, port = key.split(":")
                registry.add_or_update("peer", ip, int(port))
                registry.remove_by_key(key)
                index += 1
        except BaseException as exc:  # pragma: no cover - assertion captures thread failure
            failures.append(exc)

    thread = threading.Thread(target=mutate)
    thread.start()
    try:
        for _ in range(2_000):
            snapshot = registry.endpoint_snapshot()
            assert isinstance(snapshot, tuple)
            assert all(isinstance(endpoint, tuple) and len(endpoint) == 2 for endpoint in snapshot)
    finally:
        stop.set()
        thread.join(timeout=1)

    assert not thread.is_alive()
    assert failures == []


def test_constructor_closes_socket_when_all_bind_attempts_fail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FailingBindSocket:
        def __init__(self) -> None:
            self.closed = False

        def setsockopt(self, *_args: object) -> None:
            pass

        def bind(self, _endpoint: tuple[str, int]) -> None:
            raise OSError("occupied")

        def close(self) -> None:
            self.closed = True

    sock = FailingBindSocket()
    monkeypatch.setattr(network.socket, "socket", lambda *_args: sock)
    monkeypatch.setattr(network.socket, "SO_REUSEPORT", None, raising=False)

    with pytest.raises(RuntimeError, match="Cannot bind"):
        NetworkManager(6200)

    assert sock.closed is True


def test_listener_survives_pending_send_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    sock = BlockingSocket()
    monkeypatch.setattr(network.socket, "socket", lambda *_args: sock)
    manager = NetworkManager(6200)
    manager.start_listen(queue.Queue())
    assert sock.recv_entered.wait(timeout=1)
    def fail_once(_data: bytes) -> None:
        raise RuntimeError("send boundary failed")

    manager.broadcast = fail_once
    manager.send_heartbeat_async(b"discovery", None)
    sock.release_recv.set()
    threading.Event().wait(0.05)

    assert manager.thread is not None
    assert manager.thread.is_alive()
    manager.shutdown()
