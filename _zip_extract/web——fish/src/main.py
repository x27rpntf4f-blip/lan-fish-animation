import sys
import os
import queue
import time
import argparse
import platform

sys.path.insert(0, os.path.dirname(__file__))

# Windows DPI awareness — prevents tiny/blurry window on high-DPI displays
if platform.system() == "Windows":
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

import pygame


def _safe_font(name, size):
    try:
        return pygame.font.SysFont(name, size)
    except Exception:
        return pygame.font.Font(None, size)


from config import load, save
from fish_entity import Fish
from renderer import draw_background, draw_all_fish, draw_hud
from audio_manager import AudioManager
from network import NetworkManager, HostRegistry
from ui import ConfigPanel
import message as msg


def _try_transfer(fish, neighbor_key, reg, net, W, H):
    if neighbor_key is None:
        return False
    target = reg.get_host_by_key(neighbor_key)
    if target is None:
        return False

    # Place fish just inside the opposite edge of the target screen
    M = 20
    if fish.x > W - M:      # exiting right → enter from left
        fish.x = M + 2
    elif fish.x < M:         # exiting left → enter from right
        fish.x = W - M - 2
    if fish.y > H - M:      # exiting bottom → enter from top
        fish.y = M + 2
    elif fish.y < M:         # exiting top → enter from bottom
        fish.y = H - M - 2

    fish.host_id = target.host_id
    data = msg.pack_transfer(reg.my_id, fish)
    net.send(target.ip, target.port, data)
    net.send(target.ip, target.port, data)  # send twice for reliability
    return True


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--port", type=int, default=0, help="UDP port (0=use config)")
    return p.parse_args()


def spawn_fish(host_id, count):
    return [Fish(host_id) for _ in range(count)]


def handle_key(key, cfg, fishes, audio, paused):
    if key == pygame.K_q:
        return False, paused
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
    return True, paused


def handle_network_message(data, addr, net, reg, fishes, screen_w, screen_h):
    """addr = (sender_ip, sender_port) from recvfrom"""
    sender_ip = addr[0]

    hdr, payload = msg.unpack_full(data)
    mtype, sender_id = hdr[0], hdr[1]

    if mtype == msg.MSG_HELLO:
        info = msg.unpack_hello(payload)
        reg.add_or_update(info["hostname"], info["ip"], info["port"])
        reg.rebuild_topology()
        # Reply with ACK
        ack = msg.pack_ack(reg.my_id, reg.my_hostname, reg.my_ip, net.port)
        net.send(info["ip"], info["port"], ack)

    elif mtype == msg.MSG_ACK:
        info = msg.unpack_ack(payload)
        reg.add_or_update(info["hostname"], info["ip"], info["port"])
        reg.rebuild_topology()
        # Broadcast updated topology to everyone
        topo_entries = [reg.my_topology_entry()]
        for h in reg.hosts.values():
            topo_entries.append({"host_id": h.host_id, "position": h.position})
        topo = msg.pack_topology(reg.my_id, topo_entries)
        net.broadcast(topo)

    elif mtype == msg.MSG_HEARTBEAT:
        reg.heartbeat(sender_ip, addr[1])

    elif mtype == msg.MSG_TOPOLOGY:
        # Topology carries (host_id, position) pairs
        # We need to match our own host_id to know our position
        entries = msg.unpack_topology(payload)
        for e in entries:
            # Find which host this entry refers to by checking our hosts
            pass
        reg.rebuild_topology()

    elif mtype == msg.MSG_TRANSFER:
        info = msg.unpack_transfer(payload)
        if any(f.fish_id == info["fish_id"] for f in fishes):
            return
        fish = Fish(host_id=reg.my_id, x=info["x"], y=info["y"])
        fish.fish_id = info["fish_id"]
        fish.direction = info["direction"]
        fish.speed = info["speed"]
        fish.size = info["size"]
        fish.color = info["color"]
        fish.x = max(0, min(screen_w, fish.x))
        fish.y = max(0, min(screen_h, fish.y))
        fish.transfer_cooldown = 1.0  # 1 second cooldown after transfer
        fishes.append(fish)

    elif mtype == msg.MSG_GOODBYE:
        key = f"{sender_ip}:{addr[1]}"
        reg.remove_by_key(key)
        reg.rebuild_topology()


def main():
    args = parse_args()
    cfg = load()

    pygame.init()
    W = int(cfg["Display"]["width"])
    H = int(cfg["Display"]["height"])
    flags = pygame.DOUBLEBUF
    fullscreen = False
    screen = pygame.display.set_mode((W, H), flags)
    pygame.display.set_caption("Network Fish — LAN Multi-Screen")

    clock = pygame.time.Clock()
    panel = ConfigPanel(W, H)
    cross_screen_enabled = True
    audio = AudioManager(volume=float(cfg["Audio"]["volume"]))
    if cfg["Audio"]["enabled"] == "true":
        audio.play()

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
            handle_network_message(data, addr, net, reg, [], W, H)
        except queue.Empty:
            time.sleep(0.05)

    reg.rebuild_topology()

    # Re-broadcast hello after topology is set so existing hosts see us
    hello2 = msg.pack_hello(reg.my_id, reg.my_hostname, reg.my_ip, net.port)
    net.broadcast(hello2)

    # ---- spawn fish ----
    fish_count = int(cfg["Fish"]["count"])
    fishes = spawn_fish(reg.my_id, fish_count)
    speed_mult = float(cfg["Fish"]["speed_multiplier"])

    running = True
    paused = False
    last_heartbeat = time.time()

    while running:
        dt = clock.tick(60) / 1000.0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_TAB:
                    panel.toggle()
                elif event.key == pygame.K_f:
                    fullscreen = not fullscreen
                    if fullscreen:
                        screen = pygame.display.set_mode((W, H), pygame.DOUBLEBUF | pygame.FULLSCREEN)
                    else:
                        screen = pygame.display.set_mode((W, H), pygame.DOUBLEBUF)
                else:
                    running, paused = handle_key(
                        event.key, cfg, fishes, audio, paused)
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
                    elif atype == "pause":
                        paused = not paused
                    elif atype == "reset":
                        fishes.clear()
                        fishes.extend(spawn_fish(reg.my_id, int(cfg["Fish"]["count"])))

        # Process incoming messages
        while not msg_queue.empty():
            data, addr = msg_queue.get_nowait()
            handle_network_message(data, addr, net, reg, fishes, W, H)

        if paused:
            draw_background(screen)
            draw_all_fish(screen, fishes)
            font = _safe_font("Arial", 36)
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
            fish.update(dt, speed_mult)
            if fish.transfer_cooldown > 0:
                fish.transfer_cooldown -= dt

            # Cross-screen transfer: check at margin boundary, before bounce
            M = 20
            transferred = False
            if cross_screen_enabled and fish.transfer_cooldown <= 0:
                if fish.x > W - M:
                    transferred = _try_transfer(fish, reg.right, reg, net, W, H)
                elif fish.x < M:
                    transferred = _try_transfer(fish, reg.left, reg, net, W, H)
                elif fish.y > H - M:
                    transferred = _try_transfer(fish, None, reg, net, W, H)
                elif fish.y < M:
                    transferred = _try_transfer(fish, None, reg, net, W, H)

            if transferred:
                to_remove.append(fish)
            else:
                fish.bounce(W, H)

        for fish in to_remove:
            fishes.remove(fish)

        # Heartbeat
        if time.time() - last_heartbeat > float(cfg["Network"]["heartbeat_interval"]):
            net.broadcast(msg.pack_heartbeat(reg.my_id))
            last_heartbeat = time.time()

        # Timeout check
        for key in reg.check_timeout(float(cfg["Network"]["heartbeat_timeout"])):
            reg.remove_by_key(key)
        reg.rebuild_topology()

        # Render
        draw_background(screen)
        draw_all_fish(screen, fishes)
        draw_hud(screen, clock.get_fps(), len(fishes),
                 reg.host_count(), reg.my_id)

        # Config panel
        mx, my = pygame.mouse.get_pos()
        panel.update(mx, my)
        panel.draw(screen, len(fishes), speed_mult, cross_screen_enabled,
                   reg.host_count(), reg.my_id, clock.get_fps())

        pygame.display.flip()

    net.broadcast(msg.pack_goodbye(reg.my_id))
    audio.stop()
    net.shutdown()
    pygame.quit()


if __name__ == "__main__":
    main()
