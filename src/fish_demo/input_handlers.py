from __future__ import annotations

import pygame

from config import save
from fish_entity import Fish


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
