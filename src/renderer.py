"""
Renderer —— 鱼群与 HUD 的纯绘制层。

本模块被 main loop 每帧调用两次：
1. `draw_all_fish(screen, fishes, sprite_mgr)`
2. `draw_hud(screen, fps, fish_count, host_count, host_id)`

性能策略（多级缓存优化）：
- **Font 缓存**：_hud_font 复用同一个 SysFont 对象，避免每帧 SDL 资源分配/泄漏
- **HUD 背景条缓存**：_hud_bg 永久缓存半透明黑底 strip
- **HUD 文字缓存**：_hud_text[key] -> (last_str, Surface)，值变化才重 render
- **FPS 节流**：FPS 文本渲染限频到 2 Hz，避免肉眼无意义的频繁更新
- **鱼缩放缓存**：在 fish 对象上挂 _scaled_cache，按 (turn_state, anim_frame) 缓存
  smoothscale 结果；size/color 不变时永远命中，避免每帧调 smoothscale

职责边界：
- 只负责"画"，不修改任何 fish 状态
- 鱼的位置/动画由 Fish.update() 推进；这里只读
"""

import time as _time
import pygame

# ── 模块级缓存 ──────────────────────────────────────────
# 全部缓存都是"惰性单例"，第一次访问时创建、之后只读。
# 这些是模块级全局变量，但仅在本文件内被读写（除 _hud_text 之外都不暴露）。

# 单一 SysFont 实例：pygame 2.6 在部分平台/字体注册表损坏时会反复创建失败甚至
# 泄漏 C 资源，因此全局复用一份并 lazy 初始化。
_hud_font = None

# HUD 顶部那块 160×92 的半透明黑底 strip；只生成一次，永久缓存
_hud_bg = None

# HUD 各行文字缓存：key -> (上一次渲染的字符串, 对应 Surface)
# 值变化时才重新 font.render()，否则直接复用旧 Surface
_hud_text = {}

# FPS 文本 re-render 节流：上一次 rebuild 的时间戳（秒）
_hud_fps_update = 0.0


def safe_font(name, size, bold=False):
    """
    创建 pygame Font，对 SysFont 失败做兜底。
    pygame 2.6.1 在 macOS/Linux 上偶发 SysFont 抛异常（字体注册表损坏/缺失），
    退回 pygame.font.Font(None, size) 用 SDL 内置默认字体，保证游戏不崩。
    """
    try:
        return pygame.font.SysFont(name, size, bold=bold)
    except Exception:
        return pygame.font.Font(None, size)


def _get_hud_font():
    """
    获取（并缓存）HUD 用的 Font 对象。
    为什么缓存：每帧创建 SysFont 会在某些 SDL 平台上泄漏 C 层 TTFFont 资源。
    """
    global _hud_font
    if _hud_font is None:
        _hud_font = safe_font("Arial", 16)
    return _hud_font


def draw_background(screen):
    """
    老接口：纯渐变背景。
    已被 BackgroundManager 取代，仅保留以兼容旧调用方。
    性能问题：这里每行一次 pygame.draw.line，对 1080p 全屏意味着 ~1080 次调用。
    建议在新代码里改用 BackgroundManager.set_gradient() 的缓存版本。
    """
    h = screen.get_height()
    for y in range(h):
        t = y / h
        r = int(5 + t * 15)
        g = int(15 + t * 40)
        b = int(60 + t * 100)
        pygame.draw.line(screen, (r, g, b), (0, y), (screen.get_width(), y))


def draw_fish(screen, fish, sprite_mgr):
    """
    绘制单条鱼。
    1) 根据 turn_state 选正向/翻转精灵
    2) 查 fish._scaled_cache[(turn_state, anim_frame)]：
       - 命中：直接 blit
       - 未命中：smoothscale 到 (size*0.7) 缩放、写入缓存
    3) 用 Rect(center=...) 让鱼"中心点"对准 (x, y) 而非左上角

    注意：这里 *不* 画颜色 tint（color 字段已存在但当前未使用），
         留作扩展位（可用 Surface.set_colorkey / 调色板实现换色）。
    """
    # ── 选精灵 ──
    if fish.turn_state == 0:
        # 面朝右 → 用正向 SpriteManager 缓存
        sprite = sprite_mgr.get_sprite(fish.fish_type, fish.anim_frame)
    else:
        # 面朝左 → 用预生成的 flipped 缓存
        sprite = sprite_mgr.get_sprite_flipped(fish.fish_type, fish.anim_frame)

    # ── 缩放缓存 ──
    # key 故意不包含 size：size 改变时整体重新计算即可（不频繁）
    cache_key = (fish.turn_state, fish.anim_frame)
    if not hasattr(fish, '_scaled_cache'):
        # 第一次画这条鱼时才挂属性，避免 __init__ 里给 Fish 加魔法字段
        fish._scaled_cache = {}
    scaled = fish._scaled_cache.get(cache_key)
    if scaled is None:
        # 缓存未命中：按 size*0.7 缩放（与 Fish._compute_radius 保持一致）
        # 最小 16×16 防止鱼"缩成点"
        scale = fish.size * 0.7
        w = max(16, int(sprite.get_width() * scale))
        h = max(16, int(sprite.get_height() * scale))
        scaled = pygame.transform.smoothscale(sprite, (w, h))
        fish._scaled_cache[cache_key] = scaled

    # ── 居中 blit ──
    # Rect(center=...) 让 (fish.x, fish.y) 描述"鱼中心"而不是"鱼左上角"，
    # 避免鱼越大越偏移的视觉问题。
    rect = scaled.get_rect(center=(int(fish.x), int(fish.y)))
    screen.blit(scaled, rect)


def draw_all_fish(screen, fishes, sprite_mgr):
    """
    批量绘制所有鱼。简单 for 循环；如鱼数 > 200 可考虑按 y 排序后分层绘制
    减少透明叠加，但本项目几十条鱼规模下不必要。
    """
    for fish in fishes:
        draw_fish(screen, fish, sprite_mgr)


def _hud_text_surf(font, key, value_str):
    """
    取 HUD 文字 Surface，按 (key, value_str) 缓存。
    - 缓存命中且字符串未变 → 返回旧 Surface（0 分配）
    - 字符串变了 → 重新 font.render 并更新缓存
    """
    entry = _hud_text.get(key)
    if entry is None or entry[0] != value_str:
        # 重新渲染：(220,220,220) 浅灰白在蓝渐变背景上对比度好
        surf = font.render(value_str, True, (220, 220, 220))
        _hud_text[key] = (value_str, surf)
    return _hud_text[key][1]


def draw_hud(screen, fps, fish_count, host_count=0, host_id=0):
    """
    绘制左上角 HUD：FPS / 鱼数 / 节点数 / 本机编号。
    渲染管线：所有文字按需缓存 + 背景条永久缓存 + FPS 节流到 2Hz。
    """
    global _hud_bg, _hud_fps_update

    font = _get_hud_font()
    now = _time.time()

    # ── 文字内容（每帧重新计算字符串，但渲染只发生在变化时）──
    fps_str = f"FPS: {int(fps)}"
    fish_str = f"fish: {fish_count}"
    host_str = f"hosts: {host_count}"
    me_str = f"me: host #{host_id}"

    # ── FPS 文本 re-render 节流 ──
    # 2 Hz (~每 0.5s) 一次足够人眼读，且彻底消除每帧 SDL 表面分配造成的卡顿。
    # 实现：把缓存里 fps 条目标记为"过期"，下一次 _hud_text_surf 会重新 render。
    if now - _hud_fps_update >= 0.5:
        _hud_text.pop("fps", None)
        _hud_fps_update = now

    # ── 取文字 Surface（命中缓存就直接返回旧 Surface）──
    fps_surf  = _hud_text_surf(font, "fps",   fps_str)
    fish_surf = _hud_text_surf(font, "fish",  fish_str)
    host_surf = _hud_text_surf(font, "hosts", host_str)
    me_surf   = _hud_text_surf(font, "me",    me_str)

    # ── 半透明黑底 strip：永久缓存 ──
    if _hud_bg is None:
        # 160×92 足够放下 4 行 16px 文字（每行 ~20px 行高，含 padding）
        _hud_bg = pygame.Surface((160, 92), pygame.SRCALPHA)
        _hud_bg.fill((0, 0, 0, 100))   # alpha=100 约 40% 透明黑

    # ── 直接 blit 到 screen（不画到中间 Surface，省一次拷贝）──
    screen.blit(_hud_bg, (6, 6))
    screen.blit(fps_surf,  (14, 12))    # 第 1 行：FPS
    screen.blit(fish_surf, (14, 32))    # 第 2 行：鱼数
    screen.blit(host_surf, (14, 52))    # 第 3 行：节点数
    screen.blit(me_surf,   (14, 72))    # 第 4 行：自己的 host_id
