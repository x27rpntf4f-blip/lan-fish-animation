"""
Fish 实体类 —— 负责单条鱼的所有运行时状态、物理运动、动画推进与碰撞半径维护。

设计要点：
1. **身份唯一**：每条鱼拥有全局唯一的 `fish_id`，由 `host_id`（创建它的主机编号）
   左移 8 位后与本机 `_id_counter` 低 8 位组合而成；这意味着同一主机最多并存
   256 条鱼，跨主机 ID 不会冲突。
2. **自驱动物理**：`update()` 用欧拉积分推动 `x/y`；方向角是连续量，由边界
   `bounce()` 镜像反射并叠加少量随机扰动来保持自然游动。
3. **动画解耦**：`anim_frame` + `anim_timer` 维护 4 帧循环；与运动 update 同帧推进，
   不依赖外部时钟。
4. **跨屏穿越状态**：`in_bridge` + `transfer_cooldown` 描述鱼是否处于“正在穿越屏幕
   边界”的中间状态，跨主机迁移时通过这两个字段抑制重复发送。
5. **缓存半径**：`collision_radius` 是热路径字段，仅在 `size` 变化时重算。

辅助常量 `MAX_ANIM_FRAMES` 描述精灵子图的最大帧数，与物理/逻辑解耦。
"""

import random
import math
import colorsys


# ──────────────────────────────────────────────────────────────────────
# 模块级常量
# ──────────────────────────────────────────────────────────────────────

# 每种鱼精灵最大支持的动画帧数。
# 老版本 Free Fish Icons 素材每个 type 提供 4 张子图（A/B/C/D/E/F），
# 故取 4 帧循环。导入的扩展类型（>=1 帧）亦兼容，缺帧时自动取模循环。
MAX_ANIM_FRAMES = 4


class Fish:
    """
    单条鱼的运行时数据 + 行为封装。

    字段分组：
    - **身份**：`fish_id`、`host_id`
    - **位置/运动**：`x, y, direction, speed, wag_phase, size`
    - **外观**：`color, fish_type, anim_frame, anim_timer, turn_state`
    - **跨屏状态**：`in_bridge, transfer_cooldown`
    - **派生缓存**：`collision_radius, _cached_size, _scaled_cache（由 renderer 注入）`
    """

    # ── 类级共享状态 ────────────────────────────────────────
    # 全局自增 ID 计数器：每实例构造一次 `+= 1`，与 `host_id` 组合得到 `fish_id`。
    _id_counter = 0

    # 兼容历史代码的 6 种内置类型；运行时实际可用类型由 SpriteManager 扫描得到。
    FISH_TYPES = ["A", "B", "C", "D", "E", "F"]
    # 由 main.py 启动时从 SpriteManager 注入真实可用 type 列表；
    # 若未注入则回落到 FISH_TYPES，保证兼容性。
    AVAILABLE_TYPES = []

    def __init__(self, host_id, x=None, y=None, fish_type=None, size=None, color=None):
        """
        构造一条鱼；任何空间/外观参数缺省则随机生成。

        参数：
        - host_id: 创建该鱼的主机编号（用于 fish_id 高位与跨屏归属）
        - x/y    : 初始坐标（缺省随机落入屏幕中部区域）
        - fish_type: 精灵类型字符串（缺省从 AVAILABLE_TYPES/FISH_TYPES 随机）
        - size   : 缩放因子（0.6~1.4 经验范围）
        - color  : RGB 元组（缺省调用 `_random_color` 生成鲜艳色）
        """
        # 组合 ID：高 8 位是 host 编号，低 8 位是本机自增序号。
        # 同主机最多 256 条鱼，多机部署时不同 host 的高位天然隔离。
        self.fish_id = (host_id << 8) | (Fish._id_counter & 0xFF)
        Fish._id_counter += 1

        # ── 空间/运动状态 ───────────────────────────────────
        # 默认起始区域刻意限制在屏幕中部（100~700 / 100~500），
        # 避免一开局就贴边触发 bounce 抖动。
        self.x = x if x is not None else random.uniform(100, 700)
        self.y = y if y is not None else random.uniform(100, 500)
        # 方向用弧度表示的连续量；`bounce()` 通过镜像反射改变它。
        self.direction = random.uniform(0, 2 * math.pi)
        # 像素/秒为单位的基础游速（叠加 speed_multiplier 后给到 update）。
        self.speed = random.uniform(60, 160)
        self.size = size if size is not None else random.uniform(0.6, 1.4)
        self.color = color if color is not None else self._random_color()
        # 创建该鱼的主机；跨屏迁移时被改写为目标 host。
        self.host_id = host_id
        # 摆尾相位：用于 renderer 端让尾鳍/身体产生周期性摆动（备用）。
        self.wag_phase = random.uniform(0, 2 * math.pi)
        # 跨屏冷却：刚被发送到对端的鱼短期内不能再触发 transfer，
        # 防止抖动/快速反弹造成的重复传输风暴。
        self.transfer_cooldown = 0.0
        # 是否正处于"跨屏桥接"中间态。True 时 update 不再做边缘反弹，
        # 直到鱼完全进入对端屏幕或被判定为越界移除。
        self.in_bridge = False

        # ── 精灵/动画状态 ───────────────────────────────────
        # 优先使用运行时可用 type 列表；空时回落内置 FISH_TYPES，
        # 兼容 SpriteManager 尚未初始化的极端情况。
        types = self.AVAILABLE_TYPES or self.FISH_TYPES
        self.fish_type = fish_type if fish_type else random.choice(types)
        # 起始随机帧，避免所有鱼同步眨眼。
        self.anim_frame = random.randint(0, 3)
        # 帧切换计时器（>0.15s 切下一帧，见 update）。
        self.anim_timer = 0.0

        # 朝向状态：0=面朝右（用正向精灵），1=面朝左（用翻转精灵）。
        # 该字段由 bounce() / 跨屏迁移共同维护，renderer 据此二选一。
        self.turn_state = 0

        # ── 派生缓存 ───────────────────────────────────────
        # collision_radius 是热路径字段（每帧被 main / renderer 读取），
        # 因此仅在 size 真正变化时调用 _compute_radius 重算。
        self._cached_size = None
        self.collision_radius = 0.0
        self._compute_radius(initial=True)

    def _random_color(self):
        """
        生成饱和度/明度较高的随机 RGB 颜色。
        使用 HSV 空间采样更容易得到视觉鲜艳的色相（hue 随机、sat/val 在中高区间），
        再转回 RGB 元组。供 color 缺省时使用。
        """
        h = random.random()
        s = random.uniform(0.6, 0.9)
        v = random.uniform(0.7, 1.0)
        r, g, b = colorsys.hsv_to_rgb(h, s, v)
        return (int(r * 255), int(g * 255), int(b * 255))

    def update(self, dt, speed_multiplier=1.0, sprite_mgr=None):
        """
        推进一条鱼一帧的状态。

        参数：
        - dt               : 帧间隔（秒），来自 main loop `clock.tick(60)/1000`
        - speed_multiplier : 全局速度倍率（来自 config，可被 UI 实时调节）
        - sprite_mgr       : 用于 size 变化时重算 collision_radius
        """
        # 1) 物理积分：x/y += (cos, sin) * speed * dt。
        # 方向角以 0=右、π/2=下 的屏幕坐标约定。
        effective_speed = self.speed * speed_multiplier
        self.x += math.cos(self.direction) * effective_speed * dt
        self.y += math.sin(self.direction) * effective_speed * dt
        # wag_phase 跟随位移累加，可用于 renderer 端做尾鳍摆动特效。
        self.wag_phase += effective_speed * dt * 0.06

        # 2) 帧动画推进：每 0.15s 切下一帧（mod 4 与 MAX_ANIM_FRAMES 对齐）。
        # 故意用固定 4 帧（即便某些 type 只有 1 帧），get_sprite 内部会取模兜底。
        self.anim_timer += dt
        if self.anim_timer > 0.15:
            self.anim_frame = (self.anim_frame + 1) % 4
            self.anim_timer = 0.0

        # 3) 半径缓存维护：仅在 size 变化且能拿到 sprite_mgr 时重算；
        # 缺 sprite_mgr 时使用构造期填的 fallback，不在此处抛错。
        if self.size != self._cached_size and sprite_mgr is not None:
            self._compute_radius(sprite_mgr=sprite_mgr)

    def bounce(self, screen_w, screen_h, margin=None):
        """
        与四壁发生碰撞时镜像反射方向角，并轻微随机扰动以避免完全可预测轨迹。

        参数：
        - screen_w/h : 当前屏幕宽高
        - margin     : 触发反弹的边缘距离（缺省用 collision_radius，使鱼身不进入墙内）

        返回：是否本帧发生过反弹（bounced）。调用方据此决定是否需要进一步处理。
        """
        r = margin if margin is not None else self.collision_radius
        bounced = False

        # 左右墙：direction 关于 x 轴对称映射为 π - direction。
        if self.x < r:
            self.x = r
            self.direction = math.pi - self.direction
            bounced = True
        elif self.x > screen_w - r:
            self.x = screen_w - r
            self.direction = math.pi - self.direction
            bounced = True

        # 上下墙：direction 关于 y 轴对称映射为 -direction。
        if self.y < r:
            self.y = r
            self.direction = -self.direction
            bounced = True
        elif self.y > screen_h - r:
            self.y = screen_h - r
            self.direction = -self.direction
            bounced = True

        # 反弹时给方向角加 [-0.3, 0.3] 弧度的随机抖动，避免多鱼"对齐泳"。
        if bounced:
            self.direction += random.uniform(-0.3, 0.3)

        # 朝向状态必须 *在* 方向角稳定后再更新，确保 renderer 不会
        # 在同帧观察到"位置已贴边但朝向仍是旧值"的不一致状态。
        self.turn_state = 1 if math.cos(self.direction) < 0 else 0

        return bounced

    def _compute_radius(self, sprite_mgr=None, initial=False):
        """
        根据当前 size + fish_type + anim_frame 重新计算碰撞半径。
        优先用 sprite_mgr 拿到真实像素尺寸换算；拿不到时回落到 `size * 70` 的估值。

        参数：
        - sprite_mgr : 精灵管理器（构造期可能为 None）
        - initial    : 是否构造期调用（仅作日志/扩展位预留，当前未使用）
        """
        self._cached_size = self.size

        if sprite_mgr is not None and sprite_mgr.get_types():
            try:
                # 取当前帧的精灵图，套用与 renderer 一致的 scale (size*0.7)，
                # 用 max(w, h)/2 作为圆形包围半径（鱼身近似椭圆的保守估计）。
                sprite = sprite_mgr.get_sprite(self.fish_type, self.anim_frame)
                scale = self.size * 0.7
                w = max(16, int(sprite.get_width() * scale))
                h = max(16, int(sprite.get_height() * scale))
                self.collision_radius = max(w, h) / 2
                return
            except Exception:
                # 任何精灵缺失/解码失败都不应让鱼"无半径"——走 fallback。
                pass

        # Fallback：纯 size 估算，构造期 SpriteManager 还没就绪时使用。
        self.collision_radius = self.size * 70
