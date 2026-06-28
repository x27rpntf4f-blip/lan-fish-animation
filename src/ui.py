import pygame
from renderer import safe_font


FONT_NAME = "Arial"
BG = (30, 30, 50, 210)
ACCENT = (80, 160, 240)
WHITE = (240, 240, 240)
DIM = (140, 140, 160)
BTN_BG = (50, 50, 70)
BTN_HOVER = (70, 70, 100)
GREEN = (80, 200, 100)
RED = (220, 80, 80)
TAB_INACTIVE = (40, 40, 60)
SEP_COLOR = (60, 60, 90)


class Button:
    def __init__(self, rect, text, color=BTN_BG, text_color=WHITE):
        self.rect = pygame.Rect(rect)
        self.text = text
        self.color = color
        self.text_color = text_color
        self.hovered = False

    def update(self, mx, my):
        self.hovered = self.rect.collidepoint(mx, my)

    def draw(self, screen, font):
        c = BTN_HOVER if self.hovered else self.color
        pygame.draw.rect(screen, c, self.rect, border_radius=4)
        pygame.draw.rect(screen, (100, 100, 130), self.rect, 1, border_radius=4)
        txt = font.render(self.text, True, self.text_color)
        r = txt.get_rect(center=self.rect.center)
        screen.blit(txt, r)

    def clicked(self):
        return self.hovered


class TabButton:
    def __init__(self, rect, text):
        self.rect = pygame.Rect(rect)
        self.text = text
        self.hovered = False
        self.active = False

    def update(self, mx, my):
        self.hovered = self.rect.collidepoint(mx, my)

    def draw(self, screen, font):
        if self.active:
            c = ACCENT
        elif self.hovered:
            c = (100, 120, 160)
        else:
            c = TAB_INACTIVE
        pygame.draw.rect(screen, c, self.rect, border_top_left_radius=4,
                         border_top_right_radius=4)
        txt = font.render(self.text, True, WHITE if self.active else DIM)
        r = txt.get_rect(center=self.rect.center)
        screen.blit(txt, r)

    def clicked(self):
        return self.hovered


class ConfigPanel:
    TAB_GENERAL = 0
    TAB_FISH = 1
    TAB_BACKGROUND = 2

    def __init__(self, screen_w, screen_h):
        self.visible = False
        self.screen_w = screen_w
        self.screen_h = screen_h
        self.font_s = safe_font(FONT_NAME, 16)
        self.font = safe_font(FONT_NAME, 20)
        self.font_h = safe_font(FONT_NAME, 24, bold=True)

        self.fish_count = 5
        self.speed_mult = 1.0
        self.cross_screen = True
        self.host_count = 1
        self.my_id = 0
        self.fps = 0
        self.current_bg_type = "gradient"
        self.fullscreen = False
        self.selected_fish_type = ""   # will be set when fish types are known
        self.selected_fish_size = 1.0

        self._sprite_mgr = None       # set externally before first draw
        self._on_import = None        # callback(display_name) -> bool

        self.active_tab = self.TAB_GENERAL
        self._all_buttons = []
        self._rebuild_buttons()
        self._rebuild_tab_buttons()

    # ── helpers ────────────────────────────────────────────

    @property
    def _px(self):
        return self.panel_rect.left

    @property
    def _py(self):
        return self.panel_rect.top

    def _btn(self, x, y, w, h, text, color=BTN_BG, text_color=WHITE):
        b = Button((self._px + x, self._py + y, w, h), text, color, text_color)
        self._all_buttons.append(b)
        return b

    def _label_rect(self, x, y, w, h):
        return pygame.Rect(self._px + x, self._py + y, w, h)

    # ── build ──────────────────────────────────────────────

    def _rebuild_tab_buttons(self):
        pw = self.panel_rect.width
        tab_w = (pw - 6) // 3
        self.tab_general = TabButton((self._px + 2, self._py - 32, tab_w, 32), "General")
        self.tab_fish    = TabButton((self._px + 2 + tab_w, self._py - 32, tab_w, 32), "Fish")
        self.tab_bg      = TabButton((self._px + 2 + tab_w * 2, self._py - 32, tab_w, 32), "Background")
        self.tab_general.active = True
        self._tabs = [self.tab_general, self.tab_fish, self.tab_bg]

    def _rebuild_buttons(self):
        self._all_buttons = []
        cx = self.screen_w // 2
        cy = self.screen_h // 2
        pw, ph = 380, 350
        self.panel_rect = pygame.Rect(cx - pw // 2, cy - ph // 2, pw, ph)

        LBL = 30
        VAL = 210

        # ---- General ----
        self.btn_fish_down = self._btn(VAL, 68, 32, 28, "-")
        self.btn_fish_up   = self._btn(VAL + 90, 68, 32, 28, "+")
        self.fish_count_rect = self._label_rect(VAL + 36, 68, 48, 28)

        self.btn_speed_down = self._btn(VAL, 112, 32, 28, "-")
        self.btn_speed_up   = self._btn(VAL + 90, 112, 32, 28, "+")
        self.speed_rect = self._label_rect(VAL + 36, 112, 48, 28)

        self.btn_cross = self._btn(VAL, 156, 112, 28, "ON")

        actions_y = 210
        btn_w = 130
        gap = 16
        self.btn_fullscreen = self._btn(LBL, actions_y, btn_w, 36, "Fullscr (F)")
        self.btn_pause      = self._btn(LBL + btn_w + gap, actions_y, btn_w, 36, "Pause (P)")
        self.btn_reset      = self._btn(LBL, actions_y + 46, btn_w, 36, "Reset (R)")
        self.btn_close = self._btn(LBL, actions_y + 92, btn_w, 36,
                                   "Close (Tab)", color=(60, 60, 80))

        # ---- Fish ----
        self._build_fish_tab_buttons()

        # ---- Background ----
        bg_y = 90
        self.btn_bg_gradient = self._btn(LBL, bg_y, 90, 28, "Gradient", color=ACCENT)
        self.btn_bg_image   = self._btn(LBL + 100, bg_y, 90, 28, "Image...")
        self.btn_bg_video   = self._btn(LBL + 200, bg_y, 90, 28, "Video...")

        # seed default selected type
        types = self._get_fish_types()
        if types and (not self.selected_fish_type or
                      self.selected_fish_type not in types):
            self.selected_fish_type = types[0]

    def _get_fish_types(self):
        """Return the current list of fish type names."""
        if self._sprite_mgr:
            return self._sprite_mgr.get_types()
        return []

    def _build_fish_tab_buttons(self):
        """(Re)build the dynamic fish-type selector and import button.
        Uses compact buttons (4 per row) so up to ~20 types fit without
        scrolling or overlapping the Add / Close buttons."""
        types = self._get_fish_types()
        LBL = 30
        ROW_GAP = 28
        BTN_W   = 60
        BTN_H   = 24
        MAX_X   = self.panel_rect.width - LBL - BTN_W

        # Clear old fish-tab buttons
        for attr in ('btn_fish_types', 'btn_import_sprites',
                     'btn_size_down', 'btn_size_up', 'btn_add_fish'):
            if hasattr(self, attr):
                val = getattr(self, attr)
                if isinstance(val, dict):
                    for b in val.values():
                        if b in self._all_buttons:
                            self._all_buttons.remove(b)
                elif val in self._all_buttons:
                    self._all_buttons.remove(val)

        self.btn_fish_types = {}
        y = 90
        x = LBL
        for ft in types:
            if x + BTN_W > MAX_X + BTN_W:
                x = LBL
                y += ROW_GAP
            self.btn_fish_types[ft] = self._btn(x, y, BTN_W, BTN_H, ft)
            x += BTN_W + 4

        # ── controls below the fish type buttons ───────────────
        base_y = y + ROW_GAP + 6 if types else 90 + 6

        self.btn_import_sprites = self._btn(LBL, base_y, 130, 28,
                                            "Import sprites...",
                                            color=(60, 80, 60))
        sz_y = base_y + 40
        VAL = 210
        self.btn_size_down = self._btn(VAL, sz_y, 28, 28, "-")
        self.btn_size_up   = self._btn(VAL + 90, sz_y, 28, 28, "+")
        self.size_disp_rect = self._label_rect(VAL + 32, sz_y, 54, 28)

        add_y = sz_y + 40
        self.btn_add_fish = self._btn(LBL, add_y, 130, 36, "Add Fish",
                                      color=(40, 120, 60))

    def refresh_fish_types(self):
        """Call after import to rebuild the fish type buttons."""
        self._rebuild_buttons()
        self._rebuild_tab_buttons()
        types = self._get_fish_types()
        if types:
            self.selected_fish_type = types[0]

    # ── tab switching ──────────────────────────────────────

    def _set_tab(self, tab_id):
        self.active_tab = tab_id
        for t in self._tabs:
            t.active = (t is {self.TAB_GENERAL: self.tab_general,
                              self.TAB_FISH: self.tab_fish,
                              self.TAB_BACKGROUND: self.tab_bg}[tab_id])

    # ── public ─────────────────────────────────────────────

    def set_sprite_manager(self, sprite_mgr):
        """Must be called before the first draw so fish type buttons exist."""
        self._sprite_mgr = sprite_mgr
        # Rebuild now so the initial fish types appear
        self._all_buttons = []
        self._rebuild_buttons()
        self._rebuild_tab_buttons()
        types = self._get_fish_types()
        if types:
            self.selected_fish_type = types[0]

    def set_on_import(self, callback):
        """*callback(display_name)* is called when the user confirms an import."""
        self._on_import = callback

    def toggle(self):
        self.visible = not self.visible
        if self.visible:
            self.active_tab = self.TAB_GENERAL
            for t in self._tabs:
                t.active = (t is self.tab_general)
        pygame.mouse.set_visible(self.visible)
        return self.visible

    def handle_click(self):
        if not self.visible:
            return None

        # tabs
        for tab_id, tab in [(self.TAB_GENERAL, self.tab_general),
                             (self.TAB_FISH, self.tab_fish),
                             (self.TAB_BACKGROUND, self.tab_bg)]:
            if tab.clicked():
                self._set_tab(tab_id)
                return None

        # General
        if self.active_tab == self.TAB_GENERAL:
            if self.btn_fish_down.clicked():
                self.fish_count = max(1, self.fish_count - 1)
                return "fish", self.fish_count
            if self.btn_fish_up.clicked():
                self.fish_count = min(20, self.fish_count + 1)
                return "fish", self.fish_count
            if self.btn_speed_down.clicked():
                self.speed_mult = max(0.5, round(self.speed_mult - 0.1, 1))
                return "speed", self.speed_mult
            if self.btn_speed_up.clicked():
                self.speed_mult = min(2.0, round(self.speed_mult + 0.1, 1))
                return "speed", self.speed_mult
            if self.btn_cross.clicked():
                self.cross_screen = not self.cross_screen
                self.btn_cross.text = "ON" if self.cross_screen else "OFF"
                self.btn_cross.color = GREEN if self.cross_screen else RED
                return "cross_screen", self.cross_screen
            if self.btn_fullscreen.clicked():
                return "fullscreen", None
            if self.btn_pause.clicked():
                return "pause", None
            if self.btn_reset.clicked():
                return "reset", None

        # Fish
        elif self.active_tab == self.TAB_FISH:
            for ft, btn in self.btn_fish_types.items():
                if btn.clicked():
                    self.selected_fish_type = ft
                    for b in self.btn_fish_types.values():
                        b.color = BTN_BG
                    btn.color = ACCENT
                    return None
            if self.btn_size_down.clicked():
                self.selected_fish_size = max(0.4, round(self.selected_fish_size - 0.1, 1))
                return None
            if self.btn_size_up.clicked():
                self.selected_fish_size = min(2.5, round(self.selected_fish_size + 0.1, 1))
                return None
            if self.btn_add_fish.clicked():
                return "add_fish", {"fish_type": self.selected_fish_type,
                                    "size": self.selected_fish_size}
            if self.btn_import_sprites.clicked():
                return "import_sprites", None

        # Background
        elif self.active_tab == self.TAB_BACKGROUND:
            if self.btn_bg_gradient.clicked():
                self.current_bg_type = "gradient"
                return "bg_type", "gradient"
            if self.btn_bg_image.clicked():
                path = self._pick_file("Select Image",
                                       [("Images", "*.png *.jpg *.jpeg *.bmp")])
                if path:
                    self.current_bg_type = "image"
                    return "bg_type", ("image", path)
                return None
            if self.btn_bg_video.clicked():
                path = self._pick_file("Select Video",
                                       [("Videos", "*.mp4 *.avi *.mov *.mkv")])
                if path:
                    self.current_bg_type = "video"
                    return "bg_type", ("video", path)
                return None

        if self.btn_close.clicked():
            self.toggle()
            return None

        if not self.panel_rect.collidepoint(pygame.mouse.get_pos()):
            self.toggle()
            return None
        return None

    def _pick_file(self, title, filetypes):
        try:
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            path = filedialog.askopenfilename(title=title, filetypes=filetypes)
            root.destroy()
            return path if path else ""
        except Exception as e:
            print(f"[UI] file dialog failed: {e}")
            return ""

    def _pick_folder(self, title):
        """Open a native directory chooser dialog."""
        try:
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.withdraw()
            root.focus_force()
            root.attributes("-topmost", True)
            root.lift()
            path = filedialog.askdirectory(title=title, parent=root)
            root.destroy()
            print(f"[UI] _pick_folder: path={repr(path)}")
            return path if path else ""
        except Exception as e:
            print(f"[UI] _pick_folder failed: {e}")
            return ""

    def _ask_string(self, title, prompt):
        """Show a simple text input dialog and return the string."""
        try:
            import tkinter as tk
            from tkinter import simpledialog
            root = tk.Tk()
            root.withdraw()
            root.focus_force()
            root.attributes("-topmost", True)
            root.lift()
            result = simpledialog.askstring(title, prompt, parent=root)
            root.destroy()
            print(f"[UI] _ask_string: result={repr(result)}")
            return result.strip() if result else ""
        except Exception as e:
            print(f"[UI] _ask_string failed: {e}")
            return ""

    def do_import(self):
        """Run the folder-pick -> name -> import flow. Returns True if
        an import was performed, so main.py can refresh everything."""
        print("[UI] do_import() called")
        folder = self._pick_folder("Select folder with fish sprite PNGs")
        if not folder:
            print("[UI] do_import: no folder selected")
            return False
        print(f"[UI] do_import: folder={folder}")

        name = self._ask_string("Sprite name", "Display name for this fish type:")
        if not name:
            print("[UI] do_import: no name given")
            return False
        print(f"[UI] do_import: name={name}")

        if self._on_import:
            ok = self._on_import(name, folder)
            print(f"[UI] do_import: _on_import returned {ok}")
            return ok
        else:
            print("[UI] do_import: self._on_import is None!")
        return False

    def set_bg_type(self, bg_type):
        self.current_bg_type = bg_type

    def update(self, mx, my):
        if not self.visible:
            return
        for b in self._all_buttons:
            b.update(mx, my)
        for t in self._tabs:
            t.update(mx, my)

    # ── draw ───────────────────────────────────────────────

    def draw(self, screen, fish_count, speed_mult, cross_screen,
             host_count, my_id, fps):
        if not self.visible:
            return

        self.fish_count = fish_count
        self.speed_mult = speed_mult
        self.cross_screen = cross_screen
        self.host_count = host_count
        self.my_id = my_id
        self.fps = fps

        self.btn_cross.text = "ON" if self.cross_screen else "OFF"
        self.btn_cross.color = GREEN if self.cross_screen else RED

        # dim
        overlay = pygame.Surface((self.screen_w, self.screen_h), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 100))
        screen.blit(overlay, (0, 0))

        # panel
        surf = pygame.Surface(self.panel_rect.size, pygame.SRCALPHA)
        surf.fill(BG)
        screen.blit(surf, self.panel_rect.topleft)
        pygame.draw.rect(screen, ACCENT, self.panel_rect, 2, border_radius=8)

        px, py = self.panel_rect.topleft
        LBL = px + 30
        VAL = px + 210

        # tabs (above panel)
        for tab in self._tabs:
            tab.draw(screen, self.font)

        # title + status
        t = self.font_h.render("Settings", True, WHITE)
        screen.blit(t, (px + 20, py + 12))
        status = (f"Hosts: {self.host_count}    Me: host #{self.my_id}    FPS: {int(self.fps)}")
        st = self.font_s.render(status, True, DIM)
        screen.blit(st, (px + 20, py + 40))

        # body
        if self.active_tab == self.TAB_GENERAL:
            self._draw_general(screen, px, py, LBL, VAL)
        elif self.active_tab == self.TAB_FISH:
            self._draw_fish(screen, px, py, LBL, VAL)
        elif self.active_tab == self.TAB_BACKGROUND:
            self._draw_bg(screen, px, py, LBL)

        # close always last
        self.btn_close.draw(screen, self.font)

    # ── per-tab draw ───────────────────────────────────────

    def _draw_general(self, screen, px, py, LBL, VAL):
        screen.blit(self.font.render("Fish count", True, WHITE), (LBL, py + 70))
        self.btn_fish_down.draw(screen, self.font)
        n = self.font.render(str(self.fish_count), True, WHITE)
        nr = n.get_rect(center=self.fish_count_rect.center)
        screen.blit(n, nr)
        self.btn_fish_up.draw(screen, self.font)

        screen.blit(self.font.render("Speed", True, WHITE), (LBL, py + 114))
        self.btn_speed_down.draw(screen, self.font)
        sv = self.font.render(f"{self.speed_mult:.1f}x", True, WHITE)
        sr = sv.get_rect(center=self.speed_rect.center)
        screen.blit(sv, sr)
        self.btn_speed_up.draw(screen, self.font)

        screen.blit(self.font.render("Cross-screen", True, WHITE), (LBL, py + 158))
        self.btn_cross.draw(screen, self.font)

        sep = py + 198
        pygame.draw.line(screen, SEP_COLOR, (LBL, sep), (px + 350, sep), 1)

        self.btn_fullscreen.draw(screen, self.font)
        self.btn_pause.draw(screen, self.font)
        self.btn_reset.draw(screen, self.font)

    def _draw_fish(self, screen, px, py, LBL, VAL):
        screen.blit(self.font.render("Fish type", True, WHITE), (LBL, py + 70))
        for ft, btn in self.btn_fish_types.items():
            btn.color = ACCENT if ft == self.selected_fish_type else BTN_BG
            btn.draw(screen, self.font)

        self.btn_import_sprites.draw(screen, self.font_s)

        screen.blit(self.font.render("Size:", True, WHITE),
                    (LBL, self.size_disp_rect.top - self._py + 2))
        self.btn_size_down.draw(screen, self.font)
        sv = self.font.render(f"{self.selected_fish_size:.1f}", True, WHITE)
        sr = sv.get_rect(center=self.size_disp_rect.center)
        screen.blit(sv, sr)
        self.btn_size_up.draw(screen, self.font)

        sep = self.btn_add_fish.rect.top - self._py - 10
        pygame.draw.line(screen, SEP_COLOR, (LBL, sep), (px + 350, sep), 1)

        self.btn_add_fish.draw(screen, self.font)

    def _draw_bg(self, screen, px, py, LBL):
        screen.blit(self.font.render("Background type", True, WHITE), (LBL, py + 70))
        for btn in (self.btn_bg_gradient, self.btn_bg_image, self.btn_bg_video):
            btn.color = BTN_BG
        if self.current_bg_type == "gradient":
            self.btn_bg_gradient.color = ACCENT
        elif self.current_bg_type == "image":
            self.btn_bg_image.color = ACCENT
        elif self.current_bg_type == "video":
            self.btn_bg_video.color = ACCENT

        self.btn_bg_gradient.draw(screen, self.font)
        self.btn_bg_image.draw(screen, self.font)
        self.btn_bg_video.draw(screen, self.font)

        screen.blit(self.font_s.render("Image: PNG / JPG / BMP", True, DIM),
                    (LBL, py + 140))
        screen.blit(self.font_s.render("Video: MP4 / AVI / MOV / MKV", True, DIM),
                    (LBL, py + 163))
