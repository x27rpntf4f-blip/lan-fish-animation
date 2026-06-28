"""
BackgroundManager —— 背景子系统，支持 3 种模式：

1. **gradient**  ：内置蓝色深→浅渐变（默认，无外部依赖）
2. **image**     ：加载一张图片并按当前屏幕分辨率做 smoothscale
3. **video**     ：用 opencv-python 解码视频逐帧绘制（需 `pip install opencv-python`）

设计要点：
- 三种模式互斥，类型由 `_type` 决定，draw() 内部分支
- image 模式预 smoothscale 到屏幕尺寸，绘制时是单次 blit 而非循环
- video 模式 lazy 导入 cv2，避免未启用视频时也要装 opencv
- 任何资源加载失败（路径不存在/解码错）都回退为 gradient，不让 UI 黑屏
"""

import os
import pygame


class BackgroundManager:
    """
    背景绘制器。

    内部状态：
    - _type            : "gradient" | "image" | "video"
    - _path            : image/video 模式下的源文件路径
    - _image_surf      : image 模式预缩放后的 Surface
    - _gradient_surf   : 缓存的渐变 Surface（按需生成、按尺寸失效）
    - _video_cap       : cv2.VideoCapture 对象，仅 video 模式使用
    - _video_frame     : 最近一帧解码得到的 pygame Surface
    """

    def __init__(self, screen_w, screen_h):
        # 当前屏幕尺寸；on_resize 时会更新
        self.screen_w = screen_w
        self.screen_h = screen_h
        # 模式标识（默认 gradient）
        self._type = "gradient"
        # 资源路径（仅 image/video 模式有值）
        self._path = ""
        # 缓存：image 模式预缩放后的全屏 Surface
        self._image_surf = None
        # 缓存：按当前尺寸生成的渐变 Surface
        self._gradient_surf = None
        # 视频捕获器（cv2.VideoCapture 或 None）
        self._video_cap = None
        # 视频最近一帧（pygame Surface）
        self._video_frame = None

    # ── public API ──────────────────────────────────────────

    @property
    def bg_type(self):
        """当前背景模式字符串（给 UI 同步显示用）。"""
        return self._type

    @property
    def bg_path(self):
        """当前 image/video 的源文件路径（空字符串 = gradient）。"""
        return self._path

    def set_gradient(self):
        """
        切到内置渐变。video 模式会释放 cv2 捕获器，image 模式预缩放缓存保留
        （保留对切换体验影响很小，但节省了一次 re-scale）。
        """
        self._release_video()
        self._type = "gradient"
        self._path = ""

    def set_image(self, path):
        """
        加载并按当前屏幕分辨率预缩放一张图片作为背景。

        返回：成功 True / 失败 False（路径不存在或 pygame 加载失败）。
        失败时不会修改 _type，避免在 UI 上误显示"image"但实际仍 gradient。
        """
        if not os.path.exists(path):
            print(f"[BG] file not found: {path}")
            return False
        # 切到 image 模式前先关掉视频
        self._release_video()
        try:
            # 读原图 → smoothscale 到全屏大小
            raw = pygame.image.load(path)
            self._image_surf = pygame.transform.smoothscale(
                raw, (self.screen_w, self.screen_h))
            self._type = "image"
            self._path = path
            return True
        except pygame.error as e:
            print(f"[BG] failed to load image: {e}")
            return False

    def set_video(self, path):
        """
        用 opencv-python 打开视频文件作为动态背景。
        - 仅在 _type 改为 "video" 前 lazy 导入 cv2，没装也能正常启动游戏
        - 首帧在调用时主动预读一次，避免第一帧绘制时多卡一帧

        返回：成功 True / 失败 False（依赖未装/路径无效/解码失败）。
        """
        if not os.path.exists(path):
            print(f"[BG] file not found: {path}")
            return False
        self._release_video()
        try:
            import cv2  # noqa: F401 (lazy import)
        except ImportError:
            print("[BG] opencv-python not installed — cannot play video.")
            return False
        cap = cv2.VideoCapture(path)
        if not cap.isOpened():
            print(f"[BG] failed to open video: {path}")
            return False
        self._video_cap = cap
        self._type = "video"
        self._path = path
        # 预读首帧（循环里再 read 是从第 2 帧开始）
        self._read_video_frame()
        return True

    def on_resize(self, w, h):
        """
        屏幕尺寸变化时调用：
        - 更新内部 w/h
        - 渐变缓存失效（强制按新尺寸重绘）
        - image 模式重新调用 set_image(path) 以按新尺寸重缩放
        """
        self.screen_w = w
        self.screen_h = h
        self._gradient_surf = None
        if self._type == "image" and self._image_surf is not None:
            # set_image 会重新走 smoothscale，刷新 _image_surf
            self.set_image(self._path)

    def draw(self, screen):
        """
        把当前背景 blit 到 screen 上。
        模式分发；理论上 _type 必为三者之一，但加 gradient 兜底防止 _type 被外部破坏时黑屏。
        """
        if self._type == "gradient":
            self._draw_gradient(screen)
        elif self._type == "image":
            self._draw_image(screen)
        elif self._type == "video":
            self._draw_video(screen)
        else:
            # 防御性 fallback：未知模式一律渐变
            self._draw_gradient(screen)

    def cleanup(self):
        """
        退出时释放视频捕获器（cv2.VideoCapture 是系统级资源，必须显式 release）。
        """
        self._release_video()

    # ── internal helpers ────────────────────────────────────

    def _draw_gradient(self, screen):
        """
        蓝色深→浅竖向渐变背景。
        把整张渐变画到一张缓存 Surface 上（_gradient_surf），
        后续帧直接 blit 缓存，省去逐行 `pygame.draw.line`。
        """
        if self._gradient_surf is None:
            w, h = screen.get_width(), screen.get_height()
            surf = pygame.Surface((w, h))
            # 每行根据高度比例 t 算一个 RGB，绘一条横线
            for y in range(h):
                t = y / h
                r = int(5 + t * 15)        # 红：从 5 渐变到 20
                g = int(15 + t * 40)       # 绿：从 15 渐变到 55
                b = int(60 + t * 100)      # 蓝：从 60 渐变到 160（蓝主导 → 海面感）
                pygame.draw.line(surf, (r, g, b), (0, y), (w, y))
            self._gradient_surf = surf
        screen.blit(self._gradient_surf, (0, 0))

    def _draw_image(self, screen):
        """
        单次 blit 预缩放好的 _image_surf。
        理论上 _image_surf 不会为 None；若 set_image 失败会回到 gradient 分支。
        """
        if self._image_surf is None:
            # 防御：被外部置空时退回渐变，保证画面永远有内容
            self._draw_gradient(screen)
            return
        screen.blit(self._image_surf, (0, 0))

    def _draw_video(self, screen):
        """
        读最新一帧并 blit。视频取完一遍后自动回到第 0 帧形成循环。
        """
        if self._video_cap is None:
            self._draw_gradient(screen)
            return
        # 每次 draw 都 read 一帧，保证视频按实时节奏推进
        self._read_video_frame()
        if self._video_frame is not None:
            screen.blit(self._video_frame, (0, 0))
        else:
            # 视频结束或解码失败时回到渐变兜底
            self._draw_gradient(screen)

    def _read_video_frame(self):
        """
        从 _video_cap 读一帧并转换为 pygame Surface，缓存到 _video_frame。
        - BGR → RGB（cv2 颜色空间约定）
        - resize 到屏幕尺寸
        - 用 surfarray.make_surface 构造 pygame Surface（需要 numpy）
        - 失败时把视频释放回退到 gradient
        """
        if self._video_cap is None:
            return
        import cv2
        ret, frame = self._video_cap.read()
        if not ret:
            # 视频读完一遍 → 回到 0 帧实现无缝循环
            self._video_cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret, frame = self._video_cap.read()
            if not ret:
                # 循环也读不到，放弃视频模式
                self._release_video()
                return
        # cv2 默认 BGR，需要转 RGB 再给 pygame
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        # 等比 resize 到全屏大小（cv2.resize 不保持比例，按目标尺寸拉伸）
        frame = cv2.resize(frame, (self.screen_w, self.screen_h))
        # numpy array → pygame.Surface（注意 swapaxes(0,1) 是因为
        # numpy shape 是 (H, W, C)，pygame 需要 (W, H)）
        self._video_frame = pygame.surfarray.make_surface(
            frame.swapaxes(0, 1))

    def _release_video(self):
        """
        释放 cv2.VideoCapture 并清空缓存。多次调用安全。
        """
        if self._video_cap is not None:
            self._video_cap.release()
            self._video_cap = None
            self._video_frame = None
