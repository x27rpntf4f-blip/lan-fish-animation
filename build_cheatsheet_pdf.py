"""
生成答辩速查卡 PDF —— 单页 A4 横向，三栏布局（紧凑版）。
用 Canvas 直接绘制，完全控制位置，确保一页装下。
"""
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor, black, white
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


PDF_PATH = "/Users/chenxuanzhi/Documents/fish（finial）/渲染与精灵子系统_答辩速查卡.pdf"

# ── 中文字体注册 ──
# 优先 STHeiti（TrueType 轮廓，reportlab 兼容），Hiragino 走 CFF/PostScript 暂不支持
# TTC 是字体集合，需要指定 subfontIndex；0 = Light，1 = Medium（粗）
try:
    pdfmetrics.registerFont(TTFont("CJK", "/System/Library/Fonts/STHeiti Light.ttc", subfontIndex=0))
    pdfmetrics.registerFont(TTFont("CJK-Bold", "/System/Library/Fonts/STHeiti Medium.ttc", subfontIndex=0))
    CJK = "CJK"
    CJK_B = "CJK-Bold"
except Exception as e:
    print(f"Warning: failed to register STHeiti: {e}")
    CJK = "Helvetica"
    CJK_B = "Helvetica-Bold"

# ── 颜色 ──
TITLE_BG    = HexColor("#1f3a5f")
HEADER_BG   = HexColor("#2d5a8e")
HEADER_TXT  = white
Q_TXT       = HexColor("#0d2b4d")
A_TXT       = black
KEY_TXT     = HexColor("#9b1c1c")
TABLE_H_BG  = HexColor("#2d5a8e")
TABLE_ODD   = HexColor("#e8eef5")
TABLE_KEY   = HexColor("#fef9e7")
GRID_COLOR  = HexColor("#bbbbbb")


def draw_paragraph(c, x, y, w, text, font="CJK", size=6.5,
                   leading=7.5, color=A_TXT, bold=False):
    """简单换行绘制（按 \n 拆分），不做自动断行。"""
    c.setFont(CJK_B if bold else font, size)
    c.setFillColor(color)
    for i, line in enumerate(text.split("\n")):
        c.drawString(x, y - i * leading, line)


def wrap_text(c, text, max_width, font_name, font_size):
    """简易按字符宽度换行。"""
    words = text
    lines = []
    current = ""
    for ch in text:
        test = current + ch
        if c.stringWidth(test, font_name, font_size) <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = ch
    if current:
        lines.append(current)
    return lines


def draw_qa_block(c, x, y, w, q, a, fonts):
    """绘制一个 Q&A 小节。返回 (下一段 y 起点, 占用高度)。"""
    cur_y = y
    f_q, f_a = fonts
    # Q 行（粗体、蓝色）
    q_lines = wrap_text(c, "Q：" + q, w, f_q[0], f_q[1])
    for line in q_lines:
        c.setFont(f_q[0], f_q[1])
        c.setFillColor(Q_TXT)
        c.drawString(x, cur_y - f_q[1], line)
        cur_y -= f_q[2]
    # A 行
    a_lines = wrap_text(c, a, w, f_a[0], f_a[1])
    for line in a_lines:
        c.setFont(f_a[0], f_a[1])
        c.setFillColor(A_TXT)
        c.drawString(x + 4, cur_y - f_a[1], line)
        cur_y -= f_a[2]
    cur_y -= 1  # 段间 1pt
    return cur_y, y - cur_y


def draw_section_header(c, x, y, w, text, h=12, font_size=8):
    c.setFillColor(HEADER_BG)
    c.rect(x, y - h, w, h, fill=1, stroke=0)
    c.setFillColor(HEADER_TXT)
    c.setFont(CJK_B, font_size)
    c.drawString(x + 2, y - h + 2.5, text)
    return y - h


def draw_title_bar(c, x, y, w, text, h=16):
    c.setFillColor(TITLE_BG)
    c.rect(x, y - h, w, h, fill=1, stroke=0)
    c.setFillColor(HEADER_TXT)
    c.setFont(CJK_B, 11)
    c.drawString(x + 4, y - h + 4, text)
    return y - h


def draw_table(c, x, y, col_widths, rows, header=True,
               font_size=6, row_h=8, alt_bg=TABLE_ODD,
               col_bg=None):
    """绘制简单表格。col_bg 是每列背景色 dict {col_idx: color}。"""
    total_w = sum(col_widths)
    cur_y = y
    for ri, row in enumerate(rows):
        if ri == 0 and header:
            c.setFillColor(TABLE_H_BG)
            c.rect(x, cur_y - row_h, total_w, row_h, fill=1, stroke=0)
            c.setFillColor(HEADER_TXT)
            c.setFont(CJK_B, font_size)
        else:
            if col_bg:
                # 按列分别染色
                cx = x
                for ci, cw in enumerate(col_widths):
                    if ci in col_bg:
                        c.setFillColor(col_bg[ci])
                        c.rect(cx, cur_y - row_h, cw, row_h, fill=1, stroke=0)
                    cx += cw
            c.setFillColor(A_TXT)
            c.setFont(CJK, font_size)
        # 画文字
        cx = x
        for ci, cell in enumerate(row):
            c.setFillColor(HEADER_TXT if (ri == 0 and header) else A_TXT)
            c.setFont(CJK_B if (ri == 0 and header) else CJK, font_size)
            c.drawString(cx + 2, cur_y - row_h + 2, str(cell)[:30])
            cx += col_widths[ci]
        # 画网格
        c.setStrokeColor(GRID_COLOR)
        c.setLineWidth(0.3)
        cx = x
        for cw in col_widths:
            c.line(cx, cur_y, cx, cur_y - row_h)
            cx += cw
        c.line(x, cur_y, x + total_w, cur_y)
        c.line(x, cur_y - row_h, x + total_w, cur_y - row_h)
        cur_y -= row_h
    return cur_y


def main():
    page = landscape(A4)
    PAGE_W, PAGE_H = page
    c = canvas.Canvas(PDF_PATH, pagesize=page)

    # 边距
    M = 5 * mm
    inner_w = PAGE_W - 2 * M
    inner_h = PAGE_H - 2 * M

    # 字体定义（中文略宽于拉丁，字号相应小一些）
    F_Q = (CJK_B, 6.0, 7.2)
    F_A = (CJK, 5.6, 6.8)
    F_SECTION = (CJK_B, 7.5, 9)
    F_KEY = (CJK_B, 6.5, 8)

    # ── 标题栏 ──
    cur_y = PAGE_H - M
    cur_y = draw_title_bar(c, M, cur_y, inner_w, "渲染与精灵子系统 · 答辩速查卡（单页速查）")
    cur_y -= 2

    # ── 三栏布局 ──
    col_w = (inner_w - 4 * mm) / 3
    col_gap = 2 * mm
    col_xs = [M + i * (col_w + col_gap) for i in range(3)]
    col_top = cur_y

    # ── 数据 ──
    # col1: 一、项目总述 + 二、Fish 实体类
    col1_data = [
        ("一、项目总述", [
            ("解决什么问题？", "局域网多机协同鱼群动画；鱼从一块屏幕游到另一台机器继续游动 + 精灵按需全网同步"),
            ("架构分几层？", "网络层 network.py/message.py；资源层 sprite/background/audio_manager；实体层 fish_entity；渲染层 renderer/ui；主循环 main.py"),
            ("为什么用 pygame？", "教学场景要交可读源码，pygame 纯 Python+几百行能跑通，跨平台无依赖，答辩现场可读代码"),
        ]),
        ("二、Fish 实体类", [
            ("fish_id 编码（host_id<<8 | counter）", "高 8 位放主机号→跨机天然隔离；低 8 位本机自增→单机 ≤256 条足够；两台 host_id 都从 0 起鱼 ID 不会撞"),
            ("in_bridge vs transfer_cooldown？", "in_bridge=几何状态（穿越中不反弹）；transfer_cooldown=协议状态（2s 内禁发 TRANSFER）。一个管物理一个管网络协议，必须独立"),
            ("bounce 反射公式为什么 π-d / -d？", "左右墙：x 反向、y 保持→π-direction（关于 x 轴对称）；上下墙：y 反向、x 保持→-direction（关于 y 轴对称）"),
            ("为什么反弹加 [-0.3, 0.3] 随机扰动？", "避免多鱼'对齐泳'周期性同步；0.3 弧度 ≈±17° 打破周期但视觉仍自然"),
            ("碰撞半径为什么 max(w,h)/2？", "保守估计（最长边外接圆），保证不穿透；鱼身多数横向长，正方形外接最稳"),
            ("动画帧周期 0.15s？", "<0.1s 抽搐；>0.2s 僵硬；0.15s ≈6-7Hz 鱼鳍摆动，与真实鱼类节奏接近"),
            ("size*0.7 的 0.7 是什么？", "精灵归一化到 256² 透明画布的视觉修正系数；给鱼鳍/尾鳍留透明 padding；改 1.0 鱼会'太满'"),
            ("为什么 HSV 采样颜色？", "HSV 限制 s∈[0.6,0.9]、v∈[0.7,1.0] 排除灰暗色；RGB 全随机约 1/4 落在'脏'区间"),
        ]),
    ]

    # col2: 三、SpriteManager + 四、SpriteSyncManager
    col2_data = [
        ("三、SpriteManager", [
            ("为什么每鱼种一个子目录？", "平铺方式要带类型前缀易混；子目录天然隔离，类型名=目录名；跨平台都支持含空格目录名"),
            ("为什么预生成 flipped_frames 缓存？", "transform.flip 每帧 N 次=N 次 Surface 分配；预生成一次→运行时 O(1) 索引；CPU 25%→8%"),
            ("导入精灵为什么归一化 256×256 透明画布？", "renderer 端用统一公式 size*0.7 缩放+计算碰撞；居中等比缩放，短边留透明 padding 避免边缘裁切"),
            ("等比缩放用 256/max(w,h) 而非 min？", "长边归一保证所有精灵不超出 256² 边界；短边按比例缩放，居中后留 padding"),
            ("三层 fallback 设计理由？", "网络同步：未知 fish_type 不能让游戏崩；type 存在→正常；type 缺失→用第一 type；无素材→粉红方块；'降级而非崩溃'是长生命周期程序标配"),
            ("_migrate_if_needed 一次性迁移怎么幂等？", "判定条件：老目录存在 AND 新位置不存在；shutil.copy2 复制而非移动，老文件保留可回滚"),
        ]),
        ("四、SpriteSyncManager", [
            ("为什么用位掩码 (1<<ci) 而非 len==total？", "容忍乱序和重复到达（OR 幂等）；len==total 在'丢 1 收 2'时误判；位掩码是网络协议经典做法（XMODEM/HDLC）"),
            ("MAX_PENDING=32 为什么是 32？", "每 entry ~200-500B×32 ≈16KB 可忽略；32 个并发足够 32 对端同时拉精灵的极端场景；超限说明对端掉线，老 entry 优先淘汰"),
            ("chunk 丢失怎么办？", "当前不主动重传，不完整时该帧不落盘；对端 SPRITE_PING 会重新触发对方广播，本地可再发 SPRITE_REQ；'被动重传'简单可靠"),
            ("为什么文件名 Fish-(frame_index+1).png（0→1）？", "内部协议 0 基便于 mask 位运算；文件名 1 基符合用户直觉；两边约定不冲突"),
        ]),
    ]

    # col3: 五、BackgroundManager + 六、Renderer 多级缓存
    col3_data = [
        ("五、BackgroundManager", [
            ("为什么做三种模式？", "教室投影→渐变（干净）；PC 演示→图片（氛围）；期末展示→视频（吸睛）；一套接口让 UI 切换零成本"),
            ("import cv2 为什么要 lazy？", "cv2 包体 >50MB、启动慢数百毫秒；绝大多数用户只用 gradient/image；lazy import 让'不启用视频=零代价'"),
            ("cv2 帧怎么转 pygame Surface？", "cv2 默认 BGR，先 cvtColor(COLOR_BGR2RGB)；surfarray.make_surface 把 numpy 转 Surface；swapaxes(0,1) 是 numpy (H,W,C)→pygame (W,H)"),
            ("视频播完怎么办？", "读不到下一帧时 CAP_PROP_POS_FRAMES=0 重置循环；循环也失败→_release_video() 退到 gradient；主动选的视频不主动退，损坏/解码失败才退"),
            ("on_resize 为什么同时失效渐变缓存又重缩放 image？", "渐变按 (w,h) 像素逐行算必须重画；image 预缩放绑定屏幕尺寸，全屏切换旧图有黑边；两者同步刷新"),
        ]),
        ("六、Renderer 多级缓存", [
            ("4 级缓存分别缓存什么？", "_hud_font=SysFont 实例（永不失效）；_hud_bg=160×92 半透明黑底 strip（永不失效）；_hud_text[key]=文字 Surface（值变化重 render）；fish._scaled_cache=smoothscale 后的鱼图"),
            ("Font 缓存为什么必要？", "每帧创建 SysFont 在某些 SDL 平台会泄漏 C 层 TTFFont；复用一份既省 CPU 又省内存"),
            ("FPS 节流到 2Hz 不会'跳'吗？", "会跳但人眼察觉不到；60Hz 刷新反而'读不过来'；用视觉冗余换 CPU 的标准 trade-off"),
            ("_scaled_cache key 为什么不含 size？", "size 变化时整条鱼视觉完全变，旧缓存对不上→失效正确；size 不变时 100% 命中（这是常态）；不含 size 反而让 0.6-1.4 区间稳定命中"),
        ]),
    ]

    columns = [col1_data, col2_data, col3_data]
    fonts = (F_Q, F_A)

    # 绘制 3 列
    for ci, cdata in enumerate(columns):
        cur_y = col_top
        for section_title, qas in cdata:
            cur_y = draw_section_header(c, col_xs[ci], cur_y, col_w, section_title)
            for q, a in qas:
                cur_y, _ = draw_qa_block(c, col_xs[ci], cur_y, col_w, q, a, fonts)

    # ── 底部：性能/技巧 + 数字表 + 代码位置表 ──
    # 找到最长的列，确定底部空间
    bottom_y = M + 38 * mm  # 给底部预留 38mm
    cur_y = bottom_y + 38 * mm

    # 性能与技巧段（横跨整页）
    cur_y = draw_section_header(c, M, cur_y, inner_w, "七、性能与改进 + 应试技巧")
    perf_data = [
        ("怎么量化优化效果？", "transform.smoothscale：~1200 次/秒→~0 次/秒；800×600+20 条鱼：CPU 25%→8%；60fps 更稳"),
        ("进一步优化方向？", "短期：SpriteSync 加主动重传；中期：lz4 压缩 PNG，chunk 数降 60%；长期：消息换 protobuf，带宽再降 30-50%"),
        ("当前已知不足？", "UDP 无重传，精灵同步失败只能等下次 SPRITE_PING；transfer 期间鱼可能因反弹飞出屏幕；>50 条鱼时 alpha 合成 CPU 飙升"),
        ("现场读陌生代码的方法论？", "①看函数签名（输入输出契约）；②看 docstring（作者意图）；③看 if/else 分支（条件差异）；④代入最小例子手算一遍"),
        ("被质疑'只是调 API'怎么回击？", "举一个细节反向证明深度；例：位掩码完整性→1980s 网络协议栈经典做法→expected_mask=(1<<total)-1 制造低 total 位全 1 掩码→total>0 才有意义"),
        ("老师问'还有什么不足'怎么答？", "分 3 层：已知 bug/性能瓶颈/可靠性；答辩时坦白局限反而显得工程成熟；例：transfer 期间缺 cooldown 检查、UDP 无 checksum"),
    ]
    half_w = (inner_w - 4 * mm) / 2
    for q, a in perf_data:
        cur_y, _ = draw_qa_block(c, M, cur_y, inner_w, q, a, fonts)

    cur_y -= 2

    # 数字表 + 代码位置表（两列并排）
    numbers_data = [
        ["数字", "含义", "数字", "含义"],
        ["0.15s", "动画帧切换周期", "256", "精灵归一化画布"],
        ["0.7", "渲染视觉修正系数", "460B", "UDP chunk 大小"],
        ["70", "碰撞 fallback 系数", "32", "MAX_PENDING 上限"],
        ["8", "fish_id 低位 bit 数", "0.3", "bounce 随机扰动弧度"],
        ["2.0s", "transfer_cooldown", "2Hz", "FPS 文本限频"],
    ]
    code_data = [
        ["关键实现", "文件位置"],
        ["ID 编码", "fish_entity.py:69-70"],
        ["Bridge 状态", "main.py:539-575"],
        ["预翻转缓存", "sprite_manager.py:144-146"],
        ["位掩码判定", "sprite_sync.py:88-93"],
        ["4 级缓存", "renderer.py:30-40, 82-122"],
        ["cv2 帧转换", "background_manager.py:224-231"],
        ["Lazy import", "background_manager.py:107"],
    ]
    sub_w = (inner_w - 4 * mm) / 2
    table_x_left = M
    table_x_right = M + sub_w + 4 * mm

    end_y1 = draw_table(c, table_x_left, cur_y,
                        [sub_w * 0.27, sub_w * 0.73,
                         sub_w * 0.20, sub_w * 0.80],
                        numbers_data, header=True, font_size=6, row_h=7,
                        col_bg={0: TABLE_ODD, 2: TABLE_ODD})
    end_y2 = draw_table(c, table_x_right, cur_y,
                        [sub_w * 0.32, sub_w * 0.68],
                        code_data, header=True, font_size=6, row_h=7,
                        col_bg={0: TABLE_KEY})

    # ── 顶部 banner 强调高频重点 ──
    # 已在标题中体现

    c.showPage()
    c.save()
    print(f"PDF generated: {PDF_PATH}")


if __name__ == "__main__":
    main()
