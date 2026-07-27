from __future__ import annotations

import logging
import struct
from collections.abc import Callable

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


def test_unpack_full_rejects_surplus_payload_bytes() -> None:
    packet = message.pack_full(message.MSG_HELLO, 0, b"") + b"surplus"
    with pytest.raises(PacketDecodeError, match="payload"):
        message.unpack_full(packet)


@pytest.mark.parametrize(
    ("decoder", "payload"),
    [
        (message.unpack_hello, b""),
        (message.unpack_heartbeat, b"\x01\x03ab"),
    ],
)
def test_type_decoder_rejects_semantically_malformed_payload(decoder, payload: bytes) -> None:
    with pytest.raises(PacketDecodeError, match="payload"):
        decoder(payload)


def transfer_payload(name: bytes) -> bytes:
    prefix = struct.pack(message.TRANSFER_PREFIX_FMT, 1, 0.0, 0.0, 0.0, 1.0, 1.0, 1, 2, 3)
    return prefix + bytes([len(name)]) + name + b"\x00\x00\x01"


def sprite_chunk_payload(name: bytes) -> bytes:
    return struct.pack("!BBBBH", len(name), 0, 1, 0, 0) + name


@pytest.mark.parametrize(
    ("decoder", "payload", "message_name"),
    [
        (message.unpack_heartbeat, b"\x01\x01\xff", "HEARTBEAT"),
        (message.unpack_transfer, transfer_payload(b"\xff"), "TRANSFER"),
        (message.unpack_sprite_ping, b"\x01\x01\xff", "SPRITE_PING"),
        (message.unpack_sprite_request, b"\x01\xff", "SPRITE_REQ"),
        (message.unpack_sprite_chunk, sprite_chunk_payload(b"\xff"), "SPRITE_CHUNK"),
    ],
)
def test_type_decoder_rejects_invalid_utf8(decoder, payload: bytes, message_name: str) -> None:
    with pytest.raises(PacketDecodeError, match=message_name):
        decoder(payload)


def test_type_decoders_preserve_valid_unicode_names() -> None:
    name = "锦鲤"
    encoded = name.encode("utf-8")

    assert message.unpack_heartbeat(bytes([1, len(encoded)]) + encoded) == {"types": [name]}
    assert message.unpack_transfer(transfer_payload(encoded))["fish_type"] == name
    assert message.unpack_sprite_ping(bytes([1, len(encoded)]) + encoded) == [name]
    assert message.unpack_sprite_request(bytes([len(encoded)]) + encoded) == name
    assert message.unpack_sprite_chunk(sprite_chunk_payload(encoded))["name"] == name


LONG_MULTIBYTE_NAME = "a" * 254 + "锦"
TRUNCATED_NAME = "a" * 254


class NamedFish:
    fish_id = 1
    x = 0.0
    y = 0.0
    direction = 0.0
    speed = 1.0
    size = 1.0
    color = (1, 2, 3)
    fish_type = LONG_MULTIBYTE_NAME


def assert_name_was_truncated_safely(
    packet: bytes,
    name_length_offset: int,
    unpack_name: Callable[[bytes], str],
) -> None:
    header, payload = message.unpack_full(packet)
    assert header[3] == len(payload)
    assert payload[name_length_offset] == len(TRUNCATED_NAME.encode("utf-8")) == 254
    assert unpack_name(payload) == TRUNCATED_NAME


def test_pack_heartbeat_truncates_name_at_utf8_boundary() -> None:
    assert_name_was_truncated_safely(
        message.pack_heartbeat(1, sprite_types=[LONG_MULTIBYTE_NAME]),
        1,
        lambda payload: message.unpack_heartbeat(payload)["types"][0],
    )


def test_pack_transfer_truncates_name_at_utf8_boundary() -> None:
    assert_name_was_truncated_safely(
        message.pack_transfer(1, NamedFish()),
        message.TRANSFER_PREFIX_SIZE,
        lambda payload: message.unpack_transfer(payload)["fish_type"],
    )


def test_pack_sprite_ping_truncates_name_at_utf8_boundary() -> None:
    assert_name_was_truncated_safely(
        message.pack_sprite_ping(1, [LONG_MULTIBYTE_NAME]),
        1,
        lambda payload: message.unpack_sprite_ping(payload)[0],
    )


def test_pack_sprite_request_truncates_name_at_utf8_boundary() -> None:
    assert_name_was_truncated_safely(
        message.pack_sprite_request(1, LONG_MULTIBYTE_NAME),
        0,
        message.unpack_sprite_request,
    )


def test_pack_sprite_chunk_truncates_name_at_utf8_boundary() -> None:
    assert_name_was_truncated_safely(
        message.pack_sprite_chunk(1, LONG_MULTIBYTE_NAME, 0, 1, 0, b"data"),
        0,
        lambda payload: message.unpack_sprite_chunk(payload)["name"],
    )


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


class MutationProbe:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def __getattr__(self, name: str):
        def record_call(*args, **kwargs):
            self.calls.append(name)

        return record_call


@pytest.mark.parametrize(
    "packet",
    [
        message.pack_full(message.MSG_HELLO, 0, b""),
        message.pack_full(message.MSG_HEARTBEAT, 0, b"\x01\x03ab"),
        message.pack_full(message.MSG_HEARTBEAT, 0, b"\x01\x01\xff"),
    ],
    ids=["hello", "truncated-heartbeat", "invalid-utf8-heartbeat"],
)
def test_handler_discards_malformed_body_without_mutating_state(packet: bytes, caplog) -> None:
    registry = MutationProbe()
    untouched_fish = object()
    fishes = [untouched_fish]

    with caplog.at_level(logging.WARNING):
        main.handle_network_message(
            packet,
            ("192.0.2.10", 6000),
            MutationProbe(),
            registry,
            fishes,
            800,
            600,
            MutationProbe(),
            MutationProbe(),
        )

    assert registry.calls == []
    assert fishes == [untouched_fish]
    assert "Discarding malformed UDP packet" in caplog.text
