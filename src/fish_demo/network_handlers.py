from __future__ import annotations

import logging
import math
import os
import threading

import message as msg
from fish_entity import Fish
from fishmesh.errors import PacketDecodeError
from fishmesh.sprite_names import (
    InvalidSpriteName,
    read_regular_sprite_file,
    resolve_sprite_directory,
    validate_sprite_name,
)

BRIDGE_ZONE = 60
CHUNK_SIZE = 460  # max data bytes per SPRITE_CHUNK (keep frame < 512)
logger = logging.getLogger(__name__)


# ── sprite data sender ────────────────────────────────────


def send_sprite_data_async(sprite_mgr, net, target_ip, target_port, sender_id, sprite_name):
    """Send all PNG frames in a background thread so the main loop
    is not blocked by large UDP transfers."""
    # snapshot the net ref & data so the thread doesn't touch runtime state
    _net = net
    _ip = target_ip
    _port = target_port
    _sid = sender_id
    _name, folder = resolve_sprite_directory(sprite_mgr.SPRITE_DIR, sprite_name)
    # Read raw PNG bytes from disk — sprite_mgr.frames stores
    # Surfaces which cannot be sliced for network chunks.
    frames = []
    if os.path.isdir(folder):
        for fname in sorted(os.listdir(folder)):
            if fname.lower().startswith("fish-") and fname.lower().endswith(".png"):
                frames.append(read_regular_sprite_file(sprite_mgr.SPRITE_DIR, _name, fname))
    if not frames:
        return

    def _worker():
        for fi, raw in enumerate(frames):
            total = max(1, (len(raw) + CHUNK_SIZE - 1) // CHUNK_SIZE)
            for ci in range(total):
                start = ci * CHUNK_SIZE
                chunk_data = raw[start : start + CHUNK_SIZE]
                pkt = msg.pack_sprite_chunk(_sid, _name, fi, total, ci, chunk_data)
                _net.send(_ip, _port, pkt)

    t = threading.Thread(target=_worker, daemon=True)
    t.start()


# ── network message handler (extended) ────────────────────


def _request_missing_sprites(
    remote_types, sender_ip, sender_port, net, reg, sprite_mgr, request_tracker
):
    my_types = set(sprite_mgr.get_types())
    for remote_type in remote_types:
        try:
            remote_type = validate_sprite_name(remote_type)
        except InvalidSpriteName:
            continue
        if remote_type not in my_types and request_tracker.should_request(remote_type):
            request_tracker.mark_requested(remote_type)
            req = msg.pack_sprite_request(reg.my_id, remote_type)
            net.send(sender_ip, sender_port, req)


def handle_network_message(
    data, addr, net, reg, fishes, screen_w, screen_h, sprite_mgr, sync_mgr, request_tracker=None
):
    sender_ip = addr[0]

    try:
        hdr, payload = msg.unpack_full(data)
        mtype = hdr[0]
        if mtype in (msg.MSG_HELLO, msg.MSG_ACK):
            decoded = msg.unpack_hello(payload)
        elif mtype == msg.MSG_HEARTBEAT:
            decoded = msg.unpack_heartbeat(payload)
        elif mtype == msg.MSG_TOPOLOGY:
            decoded = msg.unpack_topology(payload)
        elif mtype == msg.MSG_TRANSFER:
            decoded = msg.unpack_transfer(payload)
        elif mtype == msg.MSG_GOODBYE:
            decoded = msg.unpack_goodbye(payload)
        elif mtype == msg.MSG_SPRITE_PING:
            decoded = msg.unpack_sprite_ping(payload)
        elif mtype == msg.MSG_SPRITE_REQ:
            decoded = msg.unpack_sprite_request(payload)
        else:
            decoded = msg.unpack_sprite_chunk(payload)
    except PacketDecodeError as exc:
        logger.warning(
            "Discarding malformed UDP packet",
            extra={
                "event": "packet_discarded",
                "peer": f"{addr[0]}:{addr[1]}",
                "error": str(exc),
            },
        )
        return

    if mtype == msg.MSG_HELLO:
        info = decoded
        # Register with self-reported IP (for heartbeat identity matching)
        # but record the actual source IP as reachable for data transmission
        reg.add_or_update(info["hostname"], info["ip"], info["port"], reachable_ip=addr[0])
        reg.rebuild_topology()
        ack = msg.pack_ack(reg.my_id, reg.my_hostname, reg.my_ip, net.port)
        # Reply to the source address that actually sent the HELLO,
        # not the self-reported IP which may be unreachable (virtual adapters)
        net.send(addr[0], addr[1], ack)

    elif mtype == msg.MSG_ACK:
        info = decoded
        reg.add_or_update(info["hostname"], info["ip"], info["port"], reachable_ip=addr[0])
        reg.rebuild_topology()
        topo_entries = [reg.my_topology_entry()]
        for h in reg.hosts.values():
            topo_entries.append(
                {"host_id": h.host_id, "position": h.position, "ip": h.reachable_ip, "port": h.port}
            )
        topo = msg.pack_topology(reg.my_id, topo_entries)
        net.broadcast(topo)

    elif mtype == msg.MSG_HEARTBEAT:
        hb_info = decoded
        # Match host identity by actual UDP source address (same approach as
        # web——fish zip: sender_ip + addr[1]).  This is more reliable than
        # self-reported IP when a machine has multiple network interfaces.
        reg.heartbeat(sender_ip, addr[1], reachable_ip=sender_ip)

        # ── heartbeat-triggered discovery ──────────────────────────
        # If this sender is not yet in our host table, proactively
        # send a HELLO to re-trigger the HELLO→ACK handshake.  This
        # gives discovery a continuous retry path via the periodic
        # heartbeat (every 3 s) instead of relying solely on the
        # one-shot startup handshake which can be lost over WiFi.
        src_key = f"{sender_ip}:{addr[1]}"
        if src_key not in reg.hosts and src_key != reg.my_key:
            known = any(
                h.reachable_ip == sender_ip and h.port == addr[1] for h in reg.hosts.values()
            )
            if not known:
                hello = msg.pack_hello(reg.my_id, reg.my_hostname, reg.my_ip, net.port)
                net.send(sender_ip, addr[1], hello)
        # ── end heartbeat-triggered discovery ──────────────────────

        if request_tracker is not None:
            _request_missing_sprites(
                hb_info["types"], sender_ip, addr[1], net, reg, sprite_mgr, request_tracker
            )

    elif mtype == msg.MSG_TOPOLOGY:
        entries = decoded
        for e in entries:
            key = f"{e['ip']}:{e['port']}"
            if key != reg.my_key and key not in reg.hosts:
                # Peer introduced by an intermediary — add to hosts
                # so the periodic discovery TOPOLOGY can also reach
                # them on the next broadcast cycle.
                reg.add_or_update("", e["ip"], e["port"], reachable_ip=e["ip"])
        reg.rebuild_topology()

    elif mtype == msg.MSG_TRANSFER:
        info = decoded
        if any(f.fish_id == info["fish_id"] for f in fishes):
            return

        src_x = info["x"]
        src_y = info["y"]
        src_w = info.get("source_screen_w", screen_w)
        heading_right = info.get("heading_right", True)

        fish = Fish(
            host_id=reg.my_id,
            x=src_x,
            y=src_y,
            fish_type=info.get(
                "fish_type", Fish.AVAILABLE_TYPES[0] if Fish.AVAILABLE_TYPES else "A"
            ),
            size=info.get("size", 1.0),
            color=info["color"],
        )
        fish.fish_id = info["fish_id"]
        fish.direction = info["direction"]
        fish.speed = info["speed"]
        # Restore facing direction from the transfer data
        fish.turn_state = 0 if heading_right else 1

        # Map source coordinate to local screen with proportional
        # mirroring.  Using the ratio (src_x / max(src_w,1)) preserves
        # correct edge-to-edge placement even when the two screens
        # have different sizes (e.g. one fullscreen 1920 px and the
        # other windowed 800 px).
        fish.x = screen_w * (1.0 - src_x / max(src_w, 1))

        # Offset spawn beyond the screen edge so the fish slides
        # smoothly *into* view rather than popping up at the border.
        # Matches the +80 / -80 removal threshold on the source side.
        if math.cos(fish.direction) >= 0:  # heading right → entering from left
            fish.x -= BRIDGE_ZONE + 20
        else:  # heading left → entering from right
            fish.x += BRIDGE_ZONE + 20

        fish.y = max(0, min(screen_h, src_y))
        fish.x = max(-200, min(screen_w + 200, fish.x))
        fish.in_bridge = True
        fish.transfer_cooldown = 2.0
        fishes.append(fish)

    elif mtype == msg.MSG_SPRITE_PING:
        if request_tracker is not None:
            _request_missing_sprites(
                decoded, sender_ip, addr[1], net, reg, sprite_mgr, request_tracker
            )

    elif mtype == msg.MSG_SPRITE_REQ:
        name = decoded
        if name and name in sprite_mgr.get_types():
            try:
                send_sprite_data_async(sprite_mgr, net, sender_ip, addr[1], reg.my_id, name)
            except InvalidSpriteName as exc:
                logger.warning(
                    "Discarding unsafe sprite request",
                    extra={
                        "event": "sprite_request_discarded",
                        "sprite_name": name,
                        "peer": f"{sender_ip}:{addr[1]}",
                        "error": str(exc),
                    },
                )

    elif mtype == msg.MSG_SPRITE_CHUNK:
        info = decoded
        try:
            complete = sync_mgr.feed_chunk(info)
        except InvalidSpriteName as exc:
            logger.warning(
                "Discarding unsafe sprite chunk",
                extra={
                    "event": "sprite_chunk_discarded",
                    "sprite_name": info["name"],
                    "frame_index": info["frame_index"],
                    "peer": f"{sender_ip}:{addr[1]}",
                    "error": str(exc),
                },
            )
            return
        if complete:
            # New sprite frame stored — rescan and update fish types
            sprite_mgr._scan_sprites_dir()
            Fish.AVAILABLE_TYPES = sprite_mgr.get_types()
            if request_tracker is not None:
                request_tracker.mark_complete(validate_sprite_name(info["name"]))
            # V1 has no total-frame manifest: one completed frame proves the
            # type is usable but cannot reveal missing later frames. M2/V2
            # owns full multi-frame completeness and recovery.

    elif mtype == msg.MSG_GOODBYE:
        key = f"{sender_ip}:{addr[1]}"
        reg.remove_by_key(key)
        reg.rebuild_topology()
