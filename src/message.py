import struct
import time
import math
import socket

MSG_HELLO        = 0x01
MSG_ACK          = 0x02
MSG_HEARTBEAT    = 0x03
MSG_TOPOLOGY     = 0x04
MSG_TRANSFER     = 0x05
MSG_GOODBYE      = 0x06
MSG_SPRITE_PING  = 0x07
MSG_SPRITE_REQ   = 0x08
MSG_SPRITE_CHUNK = 0x09

MSG_NAMES = {
    0x01: "HELLO",
    0x02: "ACK",
    0x03: "HEARTBEAT",
    0x04: "TOPOLOGY",
    0x05: "TRANSFER",
    0x06: "GOODBYE",
    0x07: "SPRITE_PING",
    0x08: "SPRITE_REQ",
    0x09: "SPRITE_CHUNK",
}

HEADER_FMT = "!BBIH"  # type, sender_id, timestamp_ms, payload_len
HEADER_SIZE = struct.calcsize(HEADER_FMT)


def pack_header(msg_type, sender_id, payload):
    ts = int(time.time() * 1000) & 0xFFFFFFFF
    return struct.pack(HEADER_FMT, msg_type, sender_id, ts, len(payload))


def unpack_header(data):
    return struct.unpack(HEADER_FMT, data[:HEADER_SIZE])


def pack_full(msg_type, sender_id, payload):
    return pack_header(msg_type, sender_id, payload) + payload


def unpack_full(data):
    hdr = unpack_header(data)
    payload = data[HEADER_SIZE:HEADER_SIZE + hdr[3]]
    return hdr, payload


# ── HELLO ──

def pack_hello(sender_id, hostname, ip_str, port):
    ip_bytes = socket.inet_aton(ip_str)
    hostname_bytes = hostname.encode("utf-8")[:32]
    payload = struct.pack("!B", len(hostname_bytes)) + hostname_bytes + ip_bytes
    payload += struct.pack("!H", port)
    return pack_full(MSG_HELLO, sender_id, payload)


def unpack_hello(payload):
    name_len = payload[0]
    hostname = payload[1:1 + name_len].decode("utf-8")
    off = 1 + name_len
    ip = socket.inet_ntoa(payload[off:off + 4])
    off += 4
    port = struct.unpack("!H", payload[off:off + 2])[0]
    return {"hostname": hostname, "ip": ip, "port": port}


# ── ACK ──

pack_ack = pack_hello
unpack_ack = unpack_hello


# ── HEARTBEAT (now carries sprite type list + sender identity for sync) ──


def pack_heartbeat(sender_id, ip_str=None, port=None, sprite_types=None):
    """Pack a heartbeat.  sprite_types is only included when non-empty
    (caller should pass None when types haven't changed).  ip_str/port
    are kept for signature compatibility but no longer embedded — the
    receiver uses the actual UDP source address instead."""
    if sprite_types:
        payload = bytearray()
        payload.append(len(sprite_types) & 0xFF)
        for name in sprite_types:
            nb = name.encode("utf-8")[:255]
            payload.append(len(nb) & 0xFF)
            payload.extend(nb)
    else:
        payload = bytearray(b"\x00")
    return pack_full(MSG_HEARTBEAT, sender_id, bytes(payload))


def unpack_heartbeat(payload):
    result = {"types": []}
    if len(payload) < 1:
        return result
    count = payload[0]
    pos = 1
    if count > 0:
        types = []
        for _ in range(count):
            if pos >= len(payload):
                break
            name_len = payload[pos]
            pos += 1
            if pos + name_len > len(payload):
                break
            name = payload[pos:pos + name_len].decode("utf-8", errors="replace")
            types.append(name)
            pos += name_len
        result["types"] = types
    return result


# ── TOPOLOGY ──

def pack_topology(sender_id, host_list):
    payload = struct.pack("!B", len(host_list))
    for h in host_list:
        ip_bytes = socket.inet_aton(h.get("ip", "0.0.0.0"))
        payload += struct.pack("!BB", h["host_id"], h["position"])
        payload += ip_bytes
        payload += struct.pack("!H", h.get("port", 0))
    return pack_full(MSG_TOPOLOGY, sender_id, payload)


def unpack_topology(payload):
    count = payload[0]
    hosts = []
    off = 1
    for _ in range(count):
        host_id, pos = struct.unpack("!BB", payload[off:off + 2])
        ip = socket.inet_ntoa(payload[off + 2:off + 6])
        port = struct.unpack("!H", payload[off + 6:off + 8])[0]
        hosts.append({"host_id": host_id, "position": pos,
                       "ip": ip, "port": port})
        off += 8
    return hosts


# ── TRANSFER ──

TRANSFER_PREFIX_FMT = "!Hfffff3B"   # fish_id thru color (10 bytes)
TRANSFER_PREFIX_SIZE = struct.calcsize(TRANSFER_PREFIX_FMT)


def pack_transfer(sender_id, fish, source_screen_w=0):
    name_bytes = fish.fish_type.encode("utf-8")[:255]
    src_hi = (source_screen_w >> 8) & 0xFF
    src_lo = source_screen_w & 0xFF
    heading_byte = 1 if math.cos(fish.direction) >= 0 else 0
    prefix = struct.pack(TRANSFER_PREFIX_FMT,
                         fish.fish_id, fish.x, fish.y, fish.direction,
                         fish.speed, fish.size, *fish.color)
    suffix = struct.pack("!B", len(name_bytes)) + name_bytes
    suffix += struct.pack("!BB", src_hi, src_lo)
    suffix += struct.pack("!B", heading_byte)
    return pack_full(MSG_TRANSFER, sender_id, prefix + suffix)


def unpack_transfer(payload):
    prefix = struct.unpack(TRANSFER_PREFIX_FMT, payload[:TRANSFER_PREFIX_SIZE])
    tail = payload[TRANSFER_PREFIX_SIZE:]

    if len(tail) >= 2:
        name_len = tail[0]
        if name_len > 0 and len(tail) >= 1 + name_len + 3:
            fish_type = tail[1:1 + name_len].decode("utf-8", errors="replace")
            rem = tail[1 + name_len:]
            src_w = (rem[0] << 8) | rem[1] if len(rem) > 1 else 0
            heading_byte = rem[2] if len(rem) > 2 else 1
        else:
            type_idx = tail[0] if len(tail) > 0 else 0
            src_lo = tail[1] if len(tail) > 1 else 0
            src_w = src_lo * 4
            heading_byte = tail[2] if len(tail) > 2 else 1
            fish_type = chr(ord("A") + type_idx) if 0 <= type_idx <= 5 else "A"
    else:
        fish_type = "A"
        src_w = tail[0] * 4 if len(tail) > 0 else 800
        heading_byte = 1

    return {
        "fish_id": prefix[0],
        "x": prefix[1],
        "y": prefix[2],
        "direction": prefix[3],
        "speed": prefix[4],
        "size": prefix[5],
        "color": (prefix[6], prefix[7], prefix[8]),
        "fish_type": fish_type,
        "source_screen_w": src_w,
        "heading_right": bool(heading_byte),
    }


# ── GOODBYE ──

def pack_goodbye(sender_id):
    return pack_full(MSG_GOODBYE, sender_id, b"")


# ── SPRITE PING ──

def pack_sprite_ping(sender_id, sprite_types):
    payload = bytearray()
    payload.append(len(sprite_types) & 0xFF)
    for name in sprite_types:
        nb = name.encode("utf-8")[:255]
        payload.append(len(nb) & 0xFF)
        payload.extend(nb)
    return pack_full(MSG_SPRITE_PING, sender_id, bytes(payload))


def unpack_sprite_ping(payload):
    if len(payload) < 1:
        return []
    count = payload[0]
    if count == 0:
        return []
    types = []
    pos = 1
    for _ in range(count):
        if pos >= len(payload):
            break
        name_len = payload[pos]
        pos += 1
        if pos + name_len > len(payload):
            break
        name = payload[pos:pos + name_len].decode("utf-8", errors="replace")
        types.append(name)
        pos += name_len
    return types


# ── SPRITE REQUEST ──

def pack_sprite_request(sender_id, sprite_name):
    nb = sprite_name.encode("utf-8")[:255]
    payload = struct.pack("!B", len(nb)) + nb
    return pack_full(MSG_SPRITE_REQ, sender_id, payload)


def unpack_sprite_request(payload):
    if len(payload) < 1:
        return ""
    name_len = payload[0]
    if name_len == 0 or len(payload) < 1 + name_len:
        return ""
    return payload[1:1 + name_len].decode("utf-8", errors="replace")


# ── SPRITE DATA CHUNK ──

def pack_sprite_chunk(sender_id, sprite_name, frame_index, total_chunks,
                      chunk_index, data):
    nb = sprite_name.encode("utf-8")[:255]
    header = struct.pack("!BBBBH",
                         len(nb),
                         frame_index,
                         total_chunks,
                         chunk_index,
                         len(data) & 0xFFFF
                         )
    return pack_full(MSG_SPRITE_CHUNK, sender_id, header + nb + data)


def unpack_sprite_chunk(payload):
    if len(payload) < 6:
        return None
    name_len, frame_idx, total, chunk_idx = \
        struct.unpack("!BBBB", payload[:4])
    data_len = struct.unpack("!H", payload[4:6])[0]
    if len(payload) < 6 + name_len + data_len:
        return None
    name = payload[6:6 + name_len].decode("utf-8", errors="replace")
    data_start = 6 + name_len
    data = payload[data_start:data_start + data_len]
    return {
        "name": name,
        "frame_index": frame_idx,
        "total_chunks": total,
        "chunk_index": chunk_idx,
        "data": data,
    }
