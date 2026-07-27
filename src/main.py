import argparse
import ctypes
import logging
import math
import os
import queue
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(__file__))

import pygame

import message as msg
from audio_manager import AudioManager
from background_manager import BackgroundManager
from config import load, save
from fish_entity import Fish
from fishmesh.errors import PacketDecodeError
from fishmesh.request_tracker import RequestTracker
from fishmesh.sprite_names import InvalidSpriteName, resolve_sprite_directory, validate_sprite_name
from network import HostRegistry, NetworkManager
from renderer import draw_all_fish, draw_background, draw_hud, safe_font
from sprite_manager import SpriteManager
from sprite_sync import SpriteSyncManager
from ui import ConfigPanel

BRIDGE_ZONE = 60
CHUNK_SIZE = 460   # max data bytes per SPRITE_CHUNK (keep frame < 512)
logger = logging.getLogger(__name__)

# ── fullscreen helpers ────────────────────────────────────


def _enter_fullscreen(cfg):
    flags = pygame.DOUBLEBUF | pygame.FULLSCREEN
    new_screen = pygame.display.set_mode((0, 0), flags)
    real_w = new_screen.get_width()
    real_h = new_screen.get_height()
    cfg["Display"]["fullscreen"] = "true"
    save(cfg)
    return new_screen, real_w, real_h


def _exit_fullscreen(cfg):
    w = int(cfg["Display"]["width"])
    h = int(cfg["Display"]["height"])
    flags = pygame.DOUBLEBUF
    new_screen = pygame.display.set_mode((w, h), flags)
    cfg["Display"]["fullscreen"] = "false"
    save(cfg)
    return new_screen, w, h


def _toggle_fullscreen(screen, cfg):
    if screen.get_flags() & pygame.FULLSCREEN:
        return _exit_fullscreen(cfg)
    else:
        return _enter_fullscreen(cfg)


def _try_transfer(fish, neighbor_key, reg, net, W, H):
    if neighbor_key is None:
        return False
    target = reg.get_host_by_key(neighbor_key)
    if target is None:
        return False

    fish.host_id = target.host_id
    data = msg.pack_transfer(reg.my_id, fish, W)
    net.send(target.reachable_ip, target.port, data)
    net.send(target.reachable_ip, target.port, data)
    return True


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--port", type=int, default=0, help="UDP port (0=use config)")
    return p.parse_args()


def spawn_fish(host_id, count):
    return [Fish(host_id) for _ in range(count)]


def handle_key(key, cfg, fishes, audio, paused, screen):
    if key == pygame.K_q:
        return False, paused, None
    if key == pygame.K_f:
        new_screen, w, h = _toggle_fullscreen(screen, cfg)
        return True, paused, ("fullscreen", new_screen, w, h)
    if key == pygame.K_m:
        audio.toggle()
    if key == pygame.K_p:
        paused = not paused
    if key == pygame.K_r:
        fishes.clear()
        fishes.extend(spawn_fish(0, int(cfg["Fish"]["count"])))
    if key == pygame.K_UP:
        n = min(20, len(fishes) + 1)
        cfg["Fish"]["count"] = str(n)
        save(cfg)
        if len(fishes) < n:
            fishes.append(Fish(0))
    if key == pygame.K_DOWN:
        n = max(1, len(fishes) - 1)
        cfg["Fish"]["count"] = str(n)
        save(cfg)
        if len(fishes) > n:
            fishes.pop()
    return True, paused, None


# ── sprite data sender ────────────────────────────────────

def _send_sprite_data_async(sprite_mgr, net, target_ip, target_port,
                            sender_id, sprite_name):
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
                path = os.path.join(folder, fname)
                with open(path, "rb") as f:
                    frames.append(f.read())
    if not frames:
        return

    def _worker():
        for fi, raw in enumerate(frames):
            total = max(1, (len(raw) + CHUNK_SIZE - 1) // CHUNK_SIZE)
            for ci in range(total):
                start = ci * CHUNK_SIZE
                chunk_data = raw[start:start + CHUNK_SIZE]
                pkt = msg.pack_sprite_chunk(_sid, _name, fi,
                                            total, ci, chunk_data)
                _net.send(_ip, _port, pkt)

    t = threading.Thread(target=_worker, daemon=True)
    t.start()


# ── network message handler (extended) ────────────────────

def _request_missing_sprites(remote_types, sender_ip, sender_port, net, reg,
                             sprite_mgr, request_tracker):
    my_types = set(sprite_mgr.get_types())
    for remote_type in remote_types:
        try:
            remote_type = validate_sprite_name(remote_type)
        except InvalidSpriteName:
            continue
        if (remote_type not in my_types and
                request_tracker.should_request(remote_type)):
            request_tracker.mark_requested(remote_type)
            req = msg.pack_sprite_request(reg.my_id, remote_type)
            net.send(sender_ip, sender_port, req)


def handle_network_message(data, addr, net, reg, fishes, screen_w, screen_h,
                           sprite_mgr, sync_mgr, request_tracker=None):
    sender_ip = addr[0]

    try:
        hdr, payload = msg.unpack_full(data)
        mtype, sender_id = hdr[0], hdr[1]
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
            "Discarding malformed UDP packet from %s:%s: %s",
            addr[0],
            addr[1],
            exc,
        )
        return

    if mtype == msg.MSG_HELLO:
        info = decoded
        # Register with self-reported IP (for heartbeat identity matching)
        # but record the actual source IP as reachable for data transmission
        reg.add_or_update(info["hostname"], info["ip"], info["port"],
                          reachable_ip=addr[0])
        reg.rebuild_topology()
        ack = msg.pack_ack(reg.my_id, reg.my_hostname, reg.my_ip, net.port)
        # Reply to the source address that actually sent the HELLO,
        # not the self-reported IP which may be unreachable (virtual adapters)
        net.send(addr[0], addr[1], ack)

    elif mtype == msg.MSG_ACK:
        info = decoded
        reg.add_or_update(info["hostname"], info["ip"], info["port"],
                          reachable_ip=addr[0])
        reg.rebuild_topology()
        topo_entries = [reg.my_topology_entry()]
        for h in reg.hosts.values():
            topo_entries.append({"host_id": h.host_id, "position": h.position,
                                 "ip": h.reachable_ip, "port": h.port})
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
            known = any(h.reachable_ip == sender_ip and h.port == addr[1]
                        for h in reg.hosts.values())
            if not known:
                hello = msg.pack_hello(reg.my_id, reg.my_hostname,
                                       reg.my_ip, net.port)
                net.send(sender_ip, addr[1], hello)
        # ── end heartbeat-triggered discovery ──────────────────────

        if request_tracker is not None:
            _request_missing_sprites(hb_info["types"], sender_ip, addr[1], net,
                                     reg, sprite_mgr, request_tracker)

    elif mtype == msg.MSG_TOPOLOGY:
        entries = decoded
        for e in entries:
            key = f"{e['ip']}:{e['port']}"
            if key != reg.my_key and key not in reg.hosts:
                # Peer introduced by an intermediary — add to hosts
                # so the periodic discovery TOPOLOGY can also reach
                # them on the next broadcast cycle.
                reg.add_or_update("", e["ip"], e["port"],
                                  reachable_ip=e["ip"])
        reg.rebuild_topology()

    elif mtype == msg.MSG_TRANSFER:
        info = decoded
        if any(f.fish_id == info["fish_id"] for f in fishes):
            return

        src_x = info["x"]
        src_y = info["y"]
        src_w = info.get("source_screen_w", screen_w)
        heading_right = info.get("heading_right", True)

        fish = Fish(host_id=reg.my_id, x=src_x, y=src_y,
                    fish_type=info.get("fish_type",
                                       Fish.AVAILABLE_TYPES[0] if Fish.AVAILABLE_TYPES else "A"),
                    size=info.get("size", 1.0),
                    color=info["color"])
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
        if math.cos(fish.direction) >= 0:      # heading right → entering from left
            fish.x -= BRIDGE_ZONE + 20
        else:                                   # heading left → entering from right
            fish.x += BRIDGE_ZONE + 20

        fish.y = max(0, min(screen_h, src_y))
        fish.x = max(-200, min(screen_w + 200, fish.x))
        fish.in_bridge = True
        fish.transfer_cooldown = 2.0
        fishes.append(fish)

    elif mtype == msg.MSG_SPRITE_PING:
        if request_tracker is not None:
            _request_missing_sprites(decoded, sender_ip, addr[1], net, reg,
                                     sprite_mgr, request_tracker)

    elif mtype == msg.MSG_SPRITE_REQ:
        name = decoded
        if name and name in sprite_mgr.get_types():
            try:
                _send_sprite_data_async(sprite_mgr, net, sender_ip, addr[1],
                                        reg.my_id, name)
            except InvalidSpriteName as exc:
                logger.warning("Discarding unsafe sprite request %r: %s", name, exc)

    elif mtype == msg.MSG_SPRITE_CHUNK:
        info = decoded
        try:
            complete = sync_mgr.feed_chunk(info)
        except InvalidSpriteName as exc:
            logger.warning("Discarding unsafe sprite chunk %r: %s", info["name"], exc)
            return
        if complete:
            # New sprite frame stored — rescan and update fish types
            sprite_mgr._scan_sprites_dir()
            Fish.AVAILABLE_TYPES = sprite_mgr.get_types()
            if request_tracker is not None:
                request_tracker.mark_complete(info["name"])
            # V1 has no total-frame manifest: one completed frame proves the
            # type is usable but cannot reveal missing later frames. M2/V2
            # owns full multi-frame completeness and recovery.

    elif mtype == msg.MSG_GOODBYE:
        key = f"{sender_ip}:{addr[1]}"
        reg.remove_by_key(key)
        reg.rebuild_topology()


def main():
    args = parse_args()
    cfg = load()

    # ── ask how many hosts to expect ──────────────────────────
    default_hosts = cfg["Network"].get("expected_hosts", "2")
    try:
        prompt = f"Number of computers in mesh (2-10) [{default_hosts}]: "
        answer = input(prompt).strip()
        if answer:
            expected = int(answer)
            expected = max(2, min(10, expected))
        else:
            expected = int(default_hosts)
    except (ValueError, EOFError):
        expected = int(default_hosts)
    cfg["Network"]["expected_hosts"] = str(expected)
    save(cfg)
    print(f"Mesh target: {expected} hosts  (broadcast until {expected} peers found)")
    # ── end host-count prompt ─────────────────────────────────

    # Raise Windows timer resolution from default ~15.6 ms → 1 ms so
    # that pygame.time.wait() / SDL_Delay() sleeps are actually honoured
    # Let SDL see the true physical resolution on high-DPI displays
    # so fullscreen fills the entire screen (no black bars).
    if sys.platform == "win32":
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            pass
        try:
            ctypes.windll.winmm.timeBeginPeriod(1)
        except Exception:
            pass

    pygame.init()
    cfg_w = int(cfg["Display"]["width"])
    cfg_h = int(cfg["Display"]["height"])
    fullscreen_start = cfg["Display"]["fullscreen"] == "true"

    if fullscreen_start:
        flags = pygame.DOUBLEBUF | pygame.FULLSCREEN
        screen = pygame.display.set_mode((0, 0), flags)
        W = screen.get_width()
        H = screen.get_height()
    else:
        flags = pygame.DOUBLEBUF
        screen = pygame.display.set_mode((cfg_w, cfg_h), flags)
        W, H = cfg_w, cfg_h

    pygame.display.set_caption("Network Fish - LAN Multi-Screen")

    clock = pygame.time.Clock()
    panel = ConfigPanel(W, H)
    cross_screen_enabled = True
    audio = AudioManager(volume=float(cfg["Audio"]["volume"]))
    if cfg["Audio"]["enabled"] == "true":
        audio.play()

    # Background init
    bg_manager = BackgroundManager(W, H)
    bg_cfg_type = cfg["Background"].get("type", "gradient")
    bg_cfg_path = cfg["Background"].get("path", "")
    if bg_cfg_type == "image" and bg_cfg_path:
        bg_manager.set_image(bg_cfg_path)
    elif bg_cfg_type == "video" and bg_cfg_path:
        bg_manager.set_video(bg_cfg_path)
    panel.set_bg_type(bg_manager.bg_type)

    # Sprite manager
    sprite_mgr = SpriteManager()
    Fish.AVAILABLE_TYPES = sprite_mgr.get_types()
    panel.set_sprite_manager(sprite_mgr)

    def _on_import_sprite(name, src_folder):
            ok = sprite_mgr.import_sprites(src_folder, name)
            if ok:
                Fish.AVAILABLE_TYPES = sprite_mgr.get_types()
                panel.refresh_fish_types()
                panel.set_bg_type(bg_manager.bg_type)
            return ok
    panel.set_on_import(_on_import_sprite)

    # Sprite sync manager — reassembles incoming chunks
    sync_mgr = SpriteSyncManager(sprite_mgr.SPRITE_DIR)
    request_tracker = RequestTracker(
        retry_after=float(cfg["Network"]["heartbeat_interval"]),
    )

    # Network init
    start_port = args.port if args.port else int(cfg["Network"]["port"])
    net = NetworkManager(start_port)
    reg = HostRegistry(net.port)
    msg_queue = queue.Queue()
    net.start_listen(msg_queue)

    # ---- discovery handshake ----
    hello = msg.pack_hello(0, reg.my_hostname, reg.my_ip, net.port)
    net.broadcast(hello)
    end = time.time() + 4.0
    while time.time() < end:
        try:
            data, addr = msg_queue.get_nowait()
            if addr[0] == reg.my_ip and addr[1] == net.port:
                continue
            handle_network_message(data, addr, net, reg, [], W, H,
                                   sprite_mgr, sync_mgr, request_tracker)
        except queue.Empty:
            time.sleep(0.05)

    reg.rebuild_topology()

    hello2 = msg.pack_hello(reg.my_id, reg.my_hostname, reg.my_ip, net.port)
    net.broadcast(hello2)

    # ---- spawn fish ----
    fish_count = int(cfg["Fish"]["count"])
    fishes = spawn_fish(reg.my_id, fish_count)
    speed_mult = float(cfg["Fish"]["speed_multiplier"])

    running = True
    paused = False
    last_heartbeat = time.time()
    last_discovery_hello = 0   # periodic discovery broadcast

    while running:
        # 60 fps aligns tick() with the 60 Hz display vsync — flip()
        # naturally paces frames at ~16.67 ms so tick() rarely needs
        # to sleep.  This sidesteps the SDL_Delay precision issue.
        dt = min(clock.tick(60) / 1000.0, 0.05)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_TAB:
                    panel.toggle()
                else:
                    running, paused, fs_action = handle_key(
                        event.key, cfg, fishes, audio, paused, screen)
                    if fs_action:
                        _, new_screen, new_w, new_h = fs_action
                        screen = new_screen
                        W, H = new_w, new_h
                        bg_manager.on_resize(W, H)
                        panel = ConfigPanel(W, H)
                        panel.set_sprite_manager(sprite_mgr)
                        panel.set_on_import(_on_import_sprite)
                        panel.set_bg_type(bg_manager.bg_type)
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                action = panel.handle_click()
                if action:
                    atype, aval = action
                    if atype == "fish":
                        n = aval
                        cfg["Fish"]["count"] = str(n)
                        save(cfg)
                        while len(fishes) < n:
                            fishes.append(Fish(reg.my_id))
                        while len(fishes) > n:
                            fishes.pop()
                    elif atype == "speed":
                        speed_mult = aval
                        cfg["Fish"]["speed_multiplier"] = str(aval)
                        save(cfg)
                    elif atype == "cross_screen":
                        cross_screen_enabled = aval
                    elif atype == "bg_type":
                        if aval == "gradient":
                            bg_manager.set_gradient()
                            cfg["Background"] = {"type": "gradient", "path": ""}
                            save(cfg)
                            panel.set_bg_type("gradient")
                        elif isinstance(aval, tuple):
                            subtype, path = aval
                            if subtype == "image":
                                ok = bg_manager.set_image(path)
                                if ok:
                                    cfg["Background"] = {"type": "image", "path": path}
                                    save(cfg)
                                    panel.set_bg_type("image")
                            elif subtype == "video":
                                ok = bg_manager.set_video(path)
                                if ok:
                                    cfg["Background"] = {"type": "video", "path": path}
                                    save(cfg)
                                    panel.set_bg_type("video")
                    elif atype == "add_fish":
                        info = aval
                        fish = Fish(reg.my_id,
                                    fish_type=info["fish_type"],
                                    size=info["size"])
                        fishes.append(fish)
                        cfg["Fish"]["count"] = str(len(fishes))
                        save(cfg)
                    elif atype == "import_sprites":
                        panel.do_import()
                    elif atype == "pause":
                        paused = not paused
                    elif atype == "fullscreen":
                        new_screen, new_w, new_h = _toggle_fullscreen(screen, cfg)
                        screen = new_screen
                        W, H = new_w, new_h
                        bg_manager.on_resize(W, H)
                        panel = ConfigPanel(W, H)
                        panel.set_sprite_manager(sprite_mgr)
                        panel.set_on_import(_on_import_sprite)
                        panel.set_bg_type(bg_manager.bg_type)
                    elif atype == "reset":
                        fishes.clear()
                        fishes.extend(spawn_fish(reg.my_id, int(cfg["Fish"]["count"])))

        # Process incoming messages
        while not msg_queue.empty():
            data, addr = msg_queue.get_nowait()
            # Skip messages from our own IP:port — self-broadcast
            # loopback.  Processing them would trigger sendto() on
            # the main thread (ACK, TOPOLOGY) and cause frame drops.
            if addr[0] == reg.my_ip and addr[1] == net.port:
                continue
            handle_network_message(data, addr, net, reg, fishes, W, H,
                                   sprite_mgr, sync_mgr, request_tracker)

        if paused:
            bg_manager.draw(screen)
            draw_all_fish(screen, fishes, sprite_mgr)
            font = safe_font("Arial", 36)
            p_text = font.render("PAUSED", True, (255, 255, 255))
            screen.blit(p_text, (W // 2 - 60, H // 2 - 18))
            draw_hud(screen, clock.get_fps(), len(fishes),
                     reg.host_count(), reg.my_id)
            mx, my = pygame.mouse.get_pos()
            panel.update(mx, my)
            panel.draw(screen, len(fishes), speed_mult, cross_screen_enabled,
                       reg.host_count(), reg.my_id, clock.get_fps())
            pygame.display.flip()
            continue

        # Update fish + cross-screen transfer
        to_remove = []
        for fish in fishes:
            fish.update(dt, speed_mult, sprite_mgr=sprite_mgr)
            if fish.transfer_cooldown > 0:
                fish.transfer_cooldown -= dt

            transferred = False
            if cross_screen_enabled and fish.transfer_cooldown <= 0:
                r = fish.collision_radius
                if fish.x > W - r and reg.right:
                    if not fish.in_bridge:
                        fish.in_bridge = True
                        _try_transfer(fish, reg.right, reg, net, W, H)
                elif fish.x < r and reg.left:
                    if not fish.in_bridge:
                        fish.in_bridge = True
                        _try_transfer(fish, reg.left, reg, net, W, H)

            if fish.in_bridge:
                r = fish.collision_radius
                exiting_right = (fish.x > W - r and
                                 math.cos(fish.direction) >= 0)
                exiting_left  = (fish.x < r and
                                 math.cos(fish.direction) < 0)
                if (exiting_right and reg.right is None) or \
                   (exiting_left  and reg.left  is None):
                    fish.in_bridge = False
                    fish.bounce(W, H)
                    continue

                if fish.x > W + 80 or fish.x < -80 or \
                   fish.y > H + 80 or fish.y < -80:
                    to_remove.append(fish)
                if fish.x > r and fish.x < W - r and \
                   fish.y > r and fish.y < H - r:
                    fish.in_bridge = False
                if fish.y < r:
                    fish.y = r
                    fish.direction = -fish.direction
                    fish.turn_state = 1 if math.cos(fish.direction) < 0 else 0
                elif fish.y > H - r:
                    fish.y = H - r
                    fish.direction = -fish.direction
                    fish.turn_state = 1 if math.cos(fish.direction) < 0 else 0
            else:
                fish.bounce(W, H)

        for fish in to_remove:
            fishes.remove(fish)

        # Heartbeat — pure unicast via network thread (no broadcast)
        # Always include sprite types so newly-joined peers can sync
        # immediately, even if this host's types haven't changed.
        if time.time() - last_heartbeat > float(cfg["Network"]["heartbeat_interval"]):
            hb = msg.pack_heartbeat(reg.my_id,
                                    sprite_types=sprite_mgr.get_types())
            net.send_heartbeat_async(hb, reg)
            last_heartbeat = time.time()

        # Periodic discovery broadcast — offloaded to network thread
        # so the main thread never calls sendto().  Stops once the
        # expected number of hosts is reached; after that pure-unicast
        # heartbeats are enough.  If a peer drops off, broadcast
        # resumes until the mesh is full again.
        if (time.time() - last_discovery_hello > 15.0 and
                reg.host_count() < expected):
            if reg.hosts:
                # Broadcast full topology so peers learn about each
                # other through us (critical for mesh when two peers
                # cannot hear each other's broadcasts directly).
                entries = [reg.my_topology_entry()]
                for h in reg.hosts.values():
                    entries.append({"host_id": h.host_id,
                                    "position": h.position,
                                    "ip": h.reachable_ip,
                                    "port": h.port})
                topo = msg.pack_topology(reg.my_id, entries)
                net.send_heartbeat_async(topo, None)
            else:
                hello = msg.pack_hello(reg.my_id, reg.my_hostname,
                                       reg.my_ip, net.port)
                net.send_heartbeat_async(hello, None)
            last_discovery_hello = time.time()

        # Timeout check
        for key in reg.check_timeout(float(cfg["Network"]["heartbeat_timeout"])):
            reg.remove_by_key(key)
        reg.rebuild_topology()

        # Render
        bg_manager.draw(screen)
        draw_all_fish(screen, fishes, sprite_mgr)
        draw_hud(screen, clock.get_fps(), len(fishes),
                 reg.host_count(), reg.my_id)

        mx, my = pygame.mouse.get_pos()
        panel.update(mx, my)
        panel.draw(screen, len(fishes), speed_mult, cross_screen_enabled,
                   reg.host_count(), reg.my_id, clock.get_fps())

        pygame.display.flip()

    net.broadcast(msg.pack_goodbye(reg.my_id))
    bg_manager.cleanup()
    audio.stop()
    net.shutdown()
    pygame.quit()


if __name__ == "__main__":
    main()
