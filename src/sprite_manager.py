"""
SpriteManager —— 鱼精灵的加载、缓存、翻转与导入。

目录约定（与 Fish.draw 强耦合）：
    <project_root>/assets/fish_sprites/
        <type_name>/
            Fish-1.png
            Fish-2.png
            ...
每个子目录代表一种鱼；按文件名升序读取的 PNG 即为该鱼的动画帧序列。
兼容老格式 `assets/Free Fish Icons/`，会在首次启动时一次性迁移。

缓存设计：
- `frames`        ：正向（面朝右）精灵列表
- `flipped_frames`：水平翻转后的精灵列表，预生成避免每帧 flip 分配新 Surface
渲染时根据 `fish.turn_state` 二选一，避免运行时 transform。
"""

import importlib.resources
import io
import logging
import os
import re
import stat
import sys
from pathlib import Path

import pygame

import message
from fishmesh.sprite_names import (
    InvalidSpriteName,
    atomic_replace_sprite_file,
    atomic_write_sprite_bytes_if_missing,
    ensure_safe_directory,
    read_regular_file,
    resolve_sprite_directory,
)

logger = logging.getLogger(__name__)


def validate_sprite_frame_bytes(frame_data: bytes) -> bytes:
    """Reject frames that cannot be represented by the V1 chunk protocol."""
    if len(frame_data) > message.MAX_SPRITE_FRAME_BYTES:
        raise InvalidSpriteName(
            f"sprite frame exceeds V1 limit of {message.MAX_SPRITE_FRAME_BYTES} bytes"
        )
    return frame_data


def _default_user_sprite_dir() -> Path:
    override = os.environ.get("FISHMESH_DATA_DIR")
    if override:
        return Path(override).expanduser() / "fish_sprites"
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        return base / "FishMesh" / "fish_sprites"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "FishMesh" / "fish_sprites"
    base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / "fishmesh" / "fish_sprites"


class SpriteManager:
    """
    精灵资源管理器。

    责任：
    1. **目录迁移**：老格式素材 → 新格式（一次性）
    2. **扫描**   ：枚举 type 子目录 + 加载 Fish-N.png
    3. **预翻转** ：为每帧预生成水平翻转版本
    4. **导入**   ：把外部 PNG 集合归一化为 256×256 透明画布并落盘
    5. **访问**   ：按 type+frame 索引取正向/翻转 Surface，含三层 fallback
    """

    PACKAGE_SPRITE_DIR = Path(
        str(importlib.resources.files("fish_demo.resources").joinpath("fish_sprites"))
    )
    # Network sync, imports, and migration always target user-writable data.
    SPRITE_DIR = _default_user_sprite_dir()
    # 老版本 Free Fish Icons 平铺目录：仅用于一次性迁移。
    OLD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "Free Fish Icons")

    def get_sprite_roots(self):
        """Return read roots in fallback-to-override order."""
        if "SPRITE_DIR" in self.__dict__:
            return [Path(self.SPRITE_DIR)]
        return [self.PACKAGE_SPRITE_DIR, Path(self.SPRITE_DIR)]

    def get_sprite_send_roots(self):
        """Return writable overrides before bundled defaults for network reads."""
        return list(reversed(self.get_sprite_roots()))

    def __init__(self):
        # type 字符串 -> 该 type 的所有帧 Surface 列表（顺序与文件名一致）
        self.frames = {}
        # type 字符串 -> 水平翻转后的帧 Surface 列表（与 frames 等长，等序）
        self.flipped_frames = {}
        # 扫描得到的有序 type 列表，UI 渲染、随机选 type 都用它
        self.fish_types = []

        # 构造期就完成迁移 + 扫描，确保 first paint 之前缓存已就绪
        self._migrate_if_needed()
        self._scan_sprites_dir()

    # ── filesystem ──────────────────────────────────────────

    def _migrate_if_needed(self):
        """
        一次性迁移老格式 → 新格式。

        触发条件：`assets/Free Fish Icons/` 存在，且由合法老格式文件
                  推导出的目标类型尚未全部具有 canonical 帧。
        动作：
            FishA-1.png, FishA-2.png, ... → fish_sprites/Fish A/Fish-1.png, ...
            FishB-1.png ...              → fish_sprites/Fish B/Fish-1.png, ...
        已存在的 canonical 文件从不覆盖；非 legacy 目标类型不影响判定。
        """
        old_root = ensure_safe_directory(self.OLD_DIR, allow_missing=True)
        if not old_root.exists():
            return
        sprite_root = ensure_safe_directory(self.SPRITE_DIR, allow_missing=True)

        legacy_frames = []
        for file_name in sorted(os.listdir(old_root)):
            match = re.fullmatch(
                r"Fish(?P<type>[A-Za-z0-9]+)-(?P<frame>\d+)\.png",
                file_name,
            )
            if match is None:
                continue
            source = old_root / file_name
            try:
                source_metadata = source.lstat()
            except FileNotFoundError:
                continue
            if not stat.S_ISREG(source_metadata.st_mode):
                continue
            target_type = f"Fish {match.group('type')}"
            target_file = f"Fish-{match.group('frame')}.png"
            legacy_frames.append((source, target_type, target_file))

        if not legacy_frames:
            return

        target_types = {target_type for _, target_type, _ in legacy_frames}

        def has_canonical_frame(target_type):
            roots = [sprite_root]
            if "SPRITE_DIR" not in self.__dict__:
                roots.append(self.PACKAGE_SPRITE_DIR)
            for root in roots:
                _, type_dir = resolve_sprite_directory(root, target_type)
                if os.path.isdir(type_dir) and any(
                    re.fullmatch(r"Fish-\d+\.png", file_name, re.IGNORECASE)
                    and os.path.isfile(os.path.join(type_dir, file_name))
                    for file_name in os.listdir(type_dir)
                ):
                    return True
            return False

        if all(has_canonical_frame(target_type) for target_type in target_types):
            return

        os.makedirs(sprite_root, exist_ok=True)
        copied = False
        for source, target_type, target_file in legacy_frames:
            try:
                source_data = read_regular_file(old_root, source.name)
            except InvalidSpriteName as exc:
                logger.warning(
                    "Skipped unsafe legacy sprite source",
                    extra={
                        "event": "sprite_migration_source_rejected",
                        "file_name": source.name,
                        "error": str(exc),
                    },
                )
                continue
            copied = (
                atomic_write_sprite_bytes_if_missing(
                    sprite_root,
                    target_type,
                    target_file,
                    source_data,
                )
                or copied
            )

        if copied:
            logger.info(
                "Migrated legacy sprite assets",
                extra={
                    "event": "sprite_migration_completed",
                    "sprite_root": os.path.basename(os.path.normpath(self.SPRITE_DIR)),
                },
            )

    def _scan_sprites_dir(self):
        """
        全量重建 self.fish_types / self.frames / self.flipped_frames。

        步骤：
        1. 清空三张表。
        2. 遍历 SPRITE_DIR 下子目录。
        3. 收集 `Fish-*.png` 文件名，按字母序作为帧序。
        4. pygame.image.load + convert_alpha 加载；失败用粉红色占位 Surface。
        5. 预生成 flipped_frames（pygame.transform.flip 比每帧调用便宜得多）。
        """
        self.fish_types = []
        self.frames = {}
        self.flipped_frames = {}

        os.makedirs(self.SPRITE_DIR, exist_ok=True)
        folders: dict[str, Path] = {}
        for root in self.get_sprite_roots():
            if not root.is_dir():
                continue
            for folder in sorted(os.listdir(root)):
                folder_path = root / folder
                if folder_path.is_dir():
                    folders[folder] = folder_path

        for folder, folder_path in sorted(folders.items()):
            if not os.path.isdir(folder_path):
                continue

            # 仅接受 Fish-N.png 命名规范的 PNG，过滤 README 等杂项
            png_files = sorted(
                f
                for f in os.listdir(folder_path)
                if f.lower().startswith("fish-") and f.lower().endswith(".png")
            )
            sendable_png_files = []
            for fname in png_files:
                try:
                    frame_data = read_regular_file(folder_path, fname)
                    validate_sprite_frame_bytes(frame_data)
                except InvalidSpriteName as exc:
                    logger.warning(
                        "Excluded unsendable sprite frame from catalog",
                        extra={
                            "event": "sprite_frame_catalog_rejected",
                            "sprite_name": folder,
                            "file_name": fname,
                            "error": str(exc),
                        },
                    )
                    continue
                sendable_png_files.append(fname)
            png_files = sendable_png_files
            if not png_files:
                continue

            # 逐帧加载；任一帧失败用 64×64 粉红色方块占位，保证后续索引安全
            frames = []
            for frame_index, fname in enumerate(png_files):
                fpath = os.path.join(folder_path, fname)
                try:
                    img = pygame.image.load(fpath).convert_alpha()
                    frames.append(img)
                except pygame.error as exc:
                    logger.warning(
                        "Using fallback for unreadable sprite frame",
                        extra={
                            "event": "sprite_frame_load_failed",
                            "sprite_name": folder,
                            "frame_index": frame_index,
                            "file_name": fname,
                            "error": str(exc),
                        },
                    )
                    fallback = pygame.Surface((64, 64), pygame.SRCALPHA)
                    fallback.fill((255, 100, 100))
                    frames.append(fallback)

            # 预生成翻转版本：与正向帧共享同一长度与顺序。
            # 一次性把 flip 结果缓存下来，渲染时直接索引。
            flipped = [pygame.transform.flip(f, True, False) for f in frames]

            self.fish_types.append(folder)
            self.frames[folder] = frames
            self.flipped_frames[folder] = flipped

        loaded = len(self.fish_types)
        logger.info(
            "Loaded sprite types",
            extra={
                "event": "sprite_catalog_loaded",
                "sprite_count": loaded,
                "sprite_root": os.path.basename(os.path.normpath(self.SPRITE_DIR)),
            },
        )

    def import_sprites(self, source_folder, display_name):
        """
        从外部目录导入一套新鱼种。

        流程：
        1. 校验源目录与 display_name。
        2. 在 SPRITE_DIR 下创建 display_name 子目录。
        3. 收集源目录里所有 PNG，按文件名升序重命名为 Fish-1.png, Fish-2.png ...
        4. 每张图：等比缩放到长边=256，居中画到 256×256 透明画布，保存。
           归一化画布大小可以让 renderer 端用统一逻辑做缩放/碰撞计算。
        5. 触发 _scan_sprites_dir() 重新加载缓存。

        返回：成功 True / 失败 False（带原因打印）。
        """
        display_name, dest = resolve_sprite_directory(self.SPRITE_DIR, display_name)
        if not os.path.isdir(source_folder):
            logger.warning(
                "Rejected sprite import source",
                extra={
                    "event": "sprite_import_rejected",
                    "sprite_name": display_name,
                    "source": os.path.basename(os.path.normpath(source_folder)),
                    "error": "source is not a directory",
                },
            )
            return False
        png_files = sorted(f for f in os.listdir(source_folder) if f.lower().endswith(".png"))
        if not png_files:
            logger.warning(
                "Rejected empty sprite import",
                extra={
                    "event": "sprite_import_rejected",
                    "sprite_name": display_name,
                    "source": os.path.basename(os.path.normpath(source_folder)),
                    "error": "source contains no PNG files",
                },
            )
            return False

        prepared_frames: list[bytes] = []
        for i, fname in enumerate(png_files, start=1):
            src = os.path.join(source_folder, fname)
            try:
                img = pygame.image.load(src).convert_alpha()
                w, h = img.get_width(), img.get_height()
                if w <= 0 or h <= 0:
                    with open(src, "rb") as source_stream:
                        frame_data = source_stream.read()
                else:
                    scale = 256.0 / max(w, h)
                    new_w = max(1, round(w * scale))
                    new_h = max(1, round(h * scale))
                    scaled = pygame.transform.smoothscale(img, (new_w, new_h))
                    canvas = pygame.Surface((256, 256), pygame.SRCALPHA)
                    ox = (256 - new_w) // 2
                    oy = (256 - new_h) // 2
                    canvas.blit(scaled, (ox, oy))
                    encoded = io.BytesIO()
                    pygame.image.save(canvas, encoded, ".png")
                    frame_data = encoded.getvalue()
            except pygame.error as exc:
                logger.warning(
                    "Copied sprite frame without normalization",
                    extra={
                        "event": "sprite_frame_import_failed",
                        "sprite_name": display_name,
                        "frame_index": i - 1,
                        "file_name": fname,
                        "error": str(exc),
                    },
                )
                with open(src, "rb") as source_stream:
                    frame_data = source_stream.read()
            prepared_frames.append(validate_sprite_frame_bytes(frame_data))

        os.makedirs(dest, exist_ok=True)
        for i, frame_data in enumerate(prepared_frames, start=1):
            new_name = f"Fish-{i}.png"

            def _write_frame(temporary_stream, data=frame_data):
                temporary_stream.write(data)

            atomic_replace_sprite_file(self.SPRITE_DIR, display_name, new_name, _write_frame)

        logger.info(
            "Imported sprite type",
            extra={
                "event": "sprite_import_completed",
                "sprite_name": display_name,
                "frame_count": len(png_files),
            },
        )
        # 触发完整 rescan：flipped_frames 等缓存一并刷新
        self._scan_sprites_dir()
        return True

    # ── sprite access ───────────────────────────────────────

    def get_types(self):
        """
        返回当前所有 fish_type 的列表拷贝。
        返回拷贝（而非 self.fish_types 引用）防止外部误改。
        """
        return list(self.fish_types)

    def get_frame_count(self, fish_type):
        """
        返回某 type 的动画帧数。未知 type 一律按 1 帧处理，
        这样 renderer 端 `anim_frame % 1 == 0` 永远不会越界。
        """
        frames = self.frames.get(fish_type)
        return len(frames) if frames else 1

    def get_sprite(self, fish_type, anim_frame):
        """
        取正向精灵 Surface。

        三层 fallback：
        1. frames[fish_type] 存在 → 取对应帧
        2. 否则取第一个可用 type 的 frames[0]（保证画面一定有东西）
        3. 仍失败 → 临时生成 64×64 粉红色 Surface 返回，绝不抛异常
        """
        frames = self.frames.get(fish_type)
        if frames is None:
            # Fallback 1：取首个可用 type
            if self.fish_types:
                frames = self.frames.get(self.fish_types[0])
            if frames is None:
                # Fallback 2：完全没素材时返回占位方块
                fb = pygame.Surface((64, 64), pygame.SRCALPHA)
                fb.fill((255, 100, 100))
                return fb
        # 帧索引取模，兼容 anim_frame 超出实际帧数的情况
        idx = int(anim_frame) % len(frames)
        return frames[idx]

    def get_sprite_flipped(self, fish_type, anim_frame):
        """
        取水平翻转后的精灵 Surface。fallback 策略与 get_sprite 对称。
        使用预生成的 flipped_frames 缓存，避免每帧再调用 pygame.transform.flip。
        """
        frames = self.flipped_frames.get(fish_type)
        if frames is None:
            if self.fish_types:
                frames = self.flipped_frames.get(self.fish_types[0])
            if frames is None:
                # 兜底：对占位方块做一次 flip 即可
                fb = pygame.Surface((64, 64), pygame.SRCALPHA)
                fb.fill((255, 100, 100))
                return pygame.transform.flip(fb, True, False)
        idx = int(anim_frame) % len(frames)
        return frames[idx]
