import ctypes
import logging
import math
import queue
import sys
import time
from collections.abc import Sequence

import pygame

import message as msg
from audio_manager import AudioManager
from background_manager import BackgroundManager
from config import load, save
from fish_demo.cli import parse_args
from fish_demo.input_handlers import _toggle_fullscreen, handle_key, spawn_fish
from fish_demo.network_handlers import handle_network_message
from fish_entity import Fish
from fishmesh.logging import configure_logging
from fishmesh.request_tracker import RequestTracker
from fishmesh.sprite_names import InvalidSpriteName
from network import HostRegistry, NetworkManager
from renderer import draw_all_fish, draw_hud, safe_font
from sprite_manager import SpriteManager
from sprite_sync import SpriteSyncManager
from ui import ConfigPanel

BRIDGE_ZONE = 60
logger = logging.getLogger(__name__)


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


def _handle_sprite_import(sprite_mgr, panel, bg_manager, name, source_folder):
    try:
        ok = sprite_mgr.import_sprites(source_folder, name)
    except InvalidSpriteName as exc:
        logger.warning(
            "Rejected invalid sprite import",
            extra={
                "event": "sprite_import_rejected",
                "sprite_name": name,
                "error": str(exc),
            },
        )
        return False
    if ok:
        Fish.AVAILABLE_TYPES = sprite_mgr.get_types()
        panel.refresh_fish_types()
        panel.set_bg_type(bg_manager.bg_type)
    return ok


class RuntimeResources:
    """Own runtime resources so every initialized stage is released exactly once."""

    def __init__(self):
        self.pygame_initialized = False
        self.audio = None
        self.background = None
        self.network = None
        self.closed = False

    @staticmethod
    def _ignore_cleanup_error(callback):
        try:
            callback()
        except Exception as exc:
            logger.exception(
                "Runtime cleanup failed",
                extra={
                    "event": "runtime_cleanup_failed",
                    "error": str(exc),
                },
            )

    def close(self):
        if self.closed:
            return
        self.closed = True

        if self.background is not None:
            self._ignore_cleanup_error(self.background.cleanup)
        if self.audio is not None:
            self._ignore_cleanup_error(self.audio.stop)
        if self.network is not None:
            self._ignore_cleanup_error(self.network.shutdown)
        if self.pygame_initialized:
            self._ignore_cleanup_error(pygame.quit)


def startup_options(cfg, args):
    """Derive diagnostic startup flags without changing persistent configuration."""
    fullscreen_start = not args.windowed and cfg["Display"]["fullscreen"] == "true"
    audio_enabled = not args.no_audio and cfg["Audio"]["enabled"] == "true"
    return fullscreen_start, audio_enabled


def _main(args, cfg, resources):
    run_deadline = time.monotonic() + args.run_seconds if args.run_seconds is not None else None

    # ── ask how many hosts to expect ──────────────────────────
    default_hosts = cfg["Network"].get("expected_hosts", "2")
    if args.expected_hosts is None:
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
    else:
        expected = args.expected_hosts
    print(f"Mesh target: {expected} hosts  (broadcast until {expected} peers found)")
    # ── end host-count prompt ─────────────────────────────────

    # Raise Windows timer resolution from default ~15.6 ms → 1 ms so
    # that pygame.time.wait() / SDL_Delay() sleeps are actually honoured
    # Let SDL see the true physical resolution on high-DPI displays
    # so fullscreen fills the entire screen (no black bars).
    if sys.platform == "win32":
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception as exc:
            logger.debug(
                "Could not enable Windows DPI awareness",
                extra={"event": "windows_dpi_setup_failed", "error": str(exc)},
            )
        try:
            ctypes.windll.winmm.timeBeginPeriod(1)
        except Exception as exc:
            logger.debug(
                "Could not enable high-resolution Windows timer",
                extra={"event": "windows_timer_setup_failed", "error": str(exc)},
            )

    resources.pygame_initialized = True
    pygame.init()
    cfg_w = int(cfg["Display"]["width"])
    cfg_h = int(cfg["Display"]["height"])
    fullscreen_start, audio_enabled = startup_options(cfg, args)

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
    resources.audio = audio
    if audio_enabled:
        audio.play()

    # Background init
    bg_manager = BackgroundManager(W, H)
    resources.background = bg_manager
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
        return _handle_sprite_import(sprite_mgr, panel, bg_manager, name, src_folder)

    panel.set_on_import(_on_import_sprite)

    # Sprite sync manager — reassembles incoming chunks
    sync_mgr = SpriteSyncManager(sprite_mgr.SPRITE_DIR)
    request_tracker = RequestTracker(
        retry_after=float(cfg["Network"]["heartbeat_interval"]),
    )

    # Network init
    start_port = args.port if args.port is not None else int(cfg["Network"]["port"])
    net = NetworkManager(start_port)
    resources.network = net
    reg = HostRegistry(net.port)
    msg_queue = queue.Queue()
    net.start_listen(msg_queue)

    # ---- discovery handshake ----
    hello = msg.pack_hello(0, reg.my_hostname, reg.my_ip, net.port)
    net.broadcast(hello)
    discovery_deadline = time.monotonic() + 4.0
    while time.monotonic() < discovery_deadline:
        if run_deadline is not None and time.monotonic() >= run_deadline:
            break
        try:
            data, addr = msg_queue.get_nowait()
            if addr[0] == reg.my_ip and addr[1] == net.port:
                continue
            handle_network_message(
                data, addr, net, reg, [], W, H, sprite_mgr, sync_mgr, request_tracker
            )
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
    last_discovery_hello = 0  # periodic discovery broadcast

    while running:
        if run_deadline is not None and time.monotonic() >= run_deadline:
            running = False
            continue

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
                        event.key, cfg, fishes, audio, paused, screen
                    )
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
                        fish = Fish(reg.my_id, fish_type=info["fish_type"], size=info["size"])
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
            handle_network_message(
                data, addr, net, reg, fishes, W, H, sprite_mgr, sync_mgr, request_tracker
            )

        if paused:
            bg_manager.draw(screen)
            draw_all_fish(screen, fishes, sprite_mgr)
            font = safe_font("Arial", 36)
            p_text = font.render("PAUSED", True, (255, 255, 255))
            screen.blit(p_text, (W // 2 - 60, H // 2 - 18))
            draw_hud(screen, clock.get_fps(), len(fishes), reg.host_count(), reg.my_id)
            mx, my = pygame.mouse.get_pos()
            panel.update(mx, my)
            panel.draw(
                screen,
                len(fishes),
                speed_mult,
                cross_screen_enabled,
                reg.host_count(),
                reg.my_id,
                clock.get_fps(),
            )
            pygame.display.flip()
            continue

        # Update fish + cross-screen transfer
        to_remove = []
        for fish in fishes:
            fish.update(dt, speed_mult, sprite_mgr=sprite_mgr)
            if fish.transfer_cooldown > 0:
                fish.transfer_cooldown -= dt

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
                exiting_right = fish.x > W - r and math.cos(fish.direction) >= 0
                exiting_left = fish.x < r and math.cos(fish.direction) < 0
                if (exiting_right and reg.right is None) or (exiting_left and reg.left is None):
                    fish.in_bridge = False
                    fish.bounce(W, H)
                    continue

                if fish.x > W + 80 or fish.x < -80 or fish.y > H + 80 or fish.y < -80:
                    to_remove.append(fish)
                if fish.x > r and fish.x < W - r and fish.y > r and fish.y < H - r:
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
            hb = msg.pack_heartbeat(reg.my_id, sprite_types=sprite_mgr.get_types())
            net.send_heartbeat_async(hb, reg)
            last_heartbeat = time.time()

        # Periodic discovery broadcast — offloaded to network thread
        # so the main thread never calls sendto().  Stops once the
        # expected number of hosts is reached; after that pure-unicast
        # heartbeats are enough.  If a peer drops off, broadcast
        # resumes until the mesh is full again.
        if time.time() - last_discovery_hello > 15.0 and reg.host_count() < expected:
            if reg.hosts:
                # Broadcast full topology so peers learn about each
                # other through us (critical for mesh when two peers
                # cannot hear each other's broadcasts directly).
                entries = [reg.my_topology_entry()]
                for h in reg.hosts.values():
                    entries.append(
                        {
                            "host_id": h.host_id,
                            "position": h.position,
                            "ip": h.reachable_ip,
                            "port": h.port,
                        }
                    )
                topo = msg.pack_topology(reg.my_id, entries)
                net.send_heartbeat_async(topo, None)
            else:
                hello = msg.pack_hello(reg.my_id, reg.my_hostname, reg.my_ip, net.port)
                net.send_heartbeat_async(hello, None)
            last_discovery_hello = time.time()

        # Timeout check
        for key in reg.check_timeout(float(cfg["Network"]["heartbeat_timeout"])):
            reg.remove_by_key(key)
        reg.rebuild_topology()

        # Render
        bg_manager.draw(screen)
        draw_all_fish(screen, fishes, sprite_mgr)
        draw_hud(screen, clock.get_fps(), len(fishes), reg.host_count(), reg.my_id)

        mx, my = pygame.mouse.get_pos()
        panel.update(mx, my)
        panel.draw(
            screen,
            len(fishes),
            speed_mult,
            cross_screen_enabled,
            reg.host_count(),
            reg.my_id,
            clock.get_fps(),
        )

        pygame.display.flip()

    try:
        net.broadcast(msg.pack_goodbye(reg.my_id))
    except Exception as exc:
        logger.exception(
            "Failed to broadcast GOODBYE during normal shutdown",
            extra={"event": "goodbye_broadcast_failed", "error": str(exc)},
        )


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    configure_logging(getattr(args, "log_level", "INFO"))
    cfg = load()
    resources = RuntimeResources()
    try:
        _main(args, cfg, resources)
    finally:
        resources.close()
    return 0
