from __future__ import annotations

import logging

import pytest

import main
import message
from fishmesh.errors import PacketDecodeError


@pytest.mark.parametrize("packet", [b"", b"\x01", b"\x01\x02\x03\x04\x05\x06\x07"])
def test_unpack_full_rejects_short_header(packet: bytes) -> None:
    with pytest.raises(PacketDecodeError, match="header"):
        message.unpack_full(packet)


def test_unpack_full_rejects_truncated_payload() -> None:
    packet = message.pack_header(message.MSG_HELLO, 0, b"12345") + b"12"
    with pytest.raises(PacketDecodeError, match="payload"):
        message.unpack_full(packet)


def test_unpack_full_rejects_unknown_message_type() -> None:
    packet = message.pack_full(0xFE, 0, b"")
    with pytest.raises(PacketDecodeError, match="message type"):
        message.unpack_full(packet)


def test_handler_discards_malformed_packet_without_mutating_state(caplog) -> None:
    untouched_fish = object()
    fishes = [untouched_fish]

    with caplog.at_level(logging.WARNING):
        main.handle_network_message(
            b"\x01",
            ("192.0.2.10", 6000),
            object(),
            object(),
            fishes,
            800,
            600,
            object(),
            object(),
        )

    assert fishes == [untouched_fish]
    assert "Discarding malformed UDP packet" in caplog.text
