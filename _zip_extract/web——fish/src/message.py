import struct
import time
import socket

MSG_HELLO     = 0x01
MSG_ACK       = 0x02
MSG_HEARTBEAT = 0x03
MSG_TOPOLOGY  = 0x04
MSG_TRANSFER  = 0x05
MSG_GOODBYE   = 0x06

MSG_NAMES = {
    0x01: "HELLO",
    0x02: "ACK",
    0x03: "HEARTBEAT",
    0x04: "TOPOLOGY",
    0x05: "TRANSFER",
    0x06: "GOODBYE",
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


# ── HEARTBEAT ──

def pack_heartbeat(sender_id):
    return pack_full(MSG_HEARTBEAT, sender_id, b"")


# ── TOPOLOGY ──

def pack_topology(sender_id, host_list):
    payload = struct.pack("!B", len(host_list))
    for h in host_list:
        payload += struct.pack("!BB", h["host_id"], h["position"])
    return pack_full(MSG_TOPOLOGY, sender_id, payload)


def unpack_topology(payload):
    count = payload[0]
    hosts = []
    off = 1
    for _ in range(count):
        host_id, pos = struct.unpack("!BB", payload[off:off + 2])
        hosts.append({"host_id": host_id, "position": pos})
        off += 2
    return hosts


# ── TRANSFER ──

TRANSFER_FMT = "!Hfffff3B"


def pack_transfer(sender_id, fish):
    payload = struct.pack(TRANSFER_FMT,
                          fish.fish_id, fish.x, fish.y, fish.direction,
                          fish.speed, fish.size, *fish.color)
    return pack_full(MSG_TRANSFER, sender_id, payload)


def unpack_transfer(payload):
    vals = struct.unpack(TRANSFER_FMT, payload)
    return {
        "fish_id": vals[0],
        "x": vals[1],
        "y": vals[2],
        "direction": vals[3],
        "speed": vals[4],
        "size": vals[5],
        "color": (vals[6], vals[7], vals[8]),
    }


# ── GOODBYE ──

def pack_goodbye(sender_id):
    return pack_full(MSG_GOODBYE, sender_id, b"")
