"""Generate experiment report based on the template."""
from docx import Document
from docx.shared import Inches, Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
import os

doc = Document()

# ── page setup ──
for section in doc.sections:
    section.top_margin = Cm(2.54)
    section.bottom_margin = Cm(2.54)
    section.left_margin = Cm(3.18)
    section.right_margin = Cm(3.18)

style = doc.styles['Normal']
font = style.font
font.name = '宋体'
font.size = Pt(12)
style.element.rPr.rFonts.set(qn('w:eastAsia'), '宋体')

# ════════════════════════════════════════════════════════════════
# COVER PAGE
# ════════════════════════════════════════════════════════════════
for _ in range(3):
    doc.add_paragraph()

p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
run = p.add_run('信息科学与工程学院')
run.font.size = Pt(18)
run.bold = True

doc.add_paragraph()

p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
run = p.add_run('课程设计报告')
run.font.size = Pt(22)
run.bold = True

doc.add_paragraph()

p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
run = p.add_run('(团队设计报告)')
run.font.size = Pt(14)

for _ in range(2):
    doc.add_paragraph()

# Info table
info_items = [
    ('项    目', '局域网多屏联动游鱼动画系统'),
    ('课程名称', '专业综合实践与训练'),
    ('专业班级', '计算机科学与技术23级'),
    ('团队名称', 'FishNet'),
    ('团队成员', '张三（组长）、李四、王五'),
    ('指导教师', ''),
]
for label, value in info_items:
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(f'{label}：{value}')
    run.font.size = Pt(14)

for _ in range(2):
    doc.add_paragraph()

p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
run = p.add_run('2026 年 6 月')
run.font.size = Pt(14)

doc.add_page_break()

# ════════════════════════════════════════════════════════════════
# TABLE OF CONTENTS
# ════════════════════════════════════════════════════════════════
p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
run = p.add_run('目  录')
run.font.size = Pt(18)
run.bold = True
doc.add_paragraph()

toc = [
    ('1  系统可行性分析', ''),
    ('    1.1  技术可行性', ''),
    ('    1.2  操作可行性', ''),
    ('2  需求分析', ''),
    ('    2.1  功能需求', ''),
    ('    2.2  非功能需求', ''),
    ('3  系统分工', ''),
    ('4  详细设计', ''),
    ('    4.1  系统架构设计', ''),
    ('    4.2  通信协议设计', ''),
    ('    4.3  组网与拓扑管理', ''),
    ('    4.4  跨屏传输机制', ''),
    ('    4.5  精灵同步机制', ''),
    ('5  系统实现', ''),
    ('    5.1  关键模块实现', ''),
    ('    5.2  帧率优化历程', ''),
    ('6  系统测试', ''),
    ('    6.1  测试环境', ''),
    ('    6.2  功能测试用例', ''),
    ('    6.3  性能测试', ''),
    ('7  总结', ''),
    ('    7.1  遇到的困难与解决', ''),
    ('    7.2  不足与展望', ''),
]
for item, _ in toc:
    doc.add_paragraph(item)

doc.add_page_break()

# ════════════════════════════════════════════════════════════════
# 1  系统可行性分析
# ════════════════════════════════════════════════════════════════

def heading(text, level=1):
    h = doc.add_heading(text, level=level)
    for run in h.runs:
        run.font.color.rgb = RGBColor(0, 0, 0)
    return h

def body(text):
    p = doc.add_paragraph()
    p.paragraph_format.first_line_indent = Pt(24)
    p.paragraph_format.line_spacing = 1.5
    run = p.add_run(text)
    run.font.size = Pt(12)
    run.font.name = '宋体'
    run.element.rPr.rFonts.set(qn('w:eastAsia'), '宋体')
    return p

heading('1  系统可行性分析', 1)

heading('1.1  技术可行性', 2)
body('本项目使用 Python 3.13 作为开发语言，pygame 2.6 作为图形渲染框架，基于 UDP Socket 实现局域网通信。Python 跨平台兼容性好，pygame 提供完善的 2D 渲染 API，UDP 广播通信适合局域网内的组网发现。相关技术成熟稳定，无技术风险。')

heading('1.2  操作可行性', 2)
body('用户通过双击 run.bat 启动程序，终端输入预期组网主机数后自动弹出游鱼窗口。窗口内可通过鼠标点击配置面板调节鱼的数量、速度、背景类型、跨屏开关等。按 F 切换全屏，按 Tab 打开设置面板。操作简单直观，无需专业知识。')

doc.add_page_break()

# ════════════════════════════════════════════════════════════════
# 2  需求分析
# ════════════════════════════════════════════════════════════════
heading('2  需求分析', 1)

heading('2.1  功能需求', 2)
body('(1) 局域网多机组网：多台连接同一 WiFi 的电脑自动发现彼此，形成线性拓扑。')
body('(2) 跨屏游鱼传输：鱼游到屏幕边缘后平滑过渡到相邻主机的显示器上继续游动。')
body('(3) 断联检测：当某台主机关闭窗口或断网时，其他主机应识别到主机数变化并更新显示。')
body('(4) 精灵同步：一台主机导入新的鱼精灵后，其他主机自动同步获取。')
body('(5) 全屏支持：支持窗口模式和全屏模式，全屏适应不同分辨率和 DPI 缩放。')
body('(6) 多媒体验：支持背景渐变/图片/视频，支持背景音乐播放。')

heading('2.2  非功能需求', 2)
body('(1) 帧率稳定：在组网运行期间应保持稳定的帧率，不能随时间逐渐降低。')
body('(2) 去中心化：任意主机先启动后启动皆可成功组网，不依赖特定主机作为服务端。')
body('(3) 网络效率：心跳通信不应对帧率产生影响，广播频率应最小化。')
body('(4) 可扩展性：支持 2-10 台主机灵活组网，支持自定义预期组网数量。')

doc.add_page_break()

# ════════════════════════════════════════════════════════════════
# 3  系统分工
# ════════════════════════════════════════════════════════════════
heading('3  系统分工', 1)

body('本小组共三人，分工如下：')

table = doc.add_table(rows=4, cols=4)
table.style = 'Table Grid'
table.alignment = WD_TABLE_ALIGNMENT.CENTER

headers = ['成员', '角色', '负责模块', '主要工作']
for i, h in enumerate(headers):
    cell = table.rows[0].cells[i]
    cell.text = h
    for p in cell.paragraphs:
        for run in p.runs:
            run.bold = True
            run.font.size = Pt(10)

data = [
    ['张三', '组长 / 核心开发',
     '网络层、组网协议',
     'UDP通信协议设计与实现、HostRegistry拓扑管理、心跳与发现机制、帧率优化、跨屏传输桥接逻辑'],
    ['李四', '开发',
     '渲染层、精灵系统',
     'SpriteManager精灵管理、SpriteSyncManager同步、BackgroundManager背景、Renderer渲染器、性能缓存优化'],
    ['王五', '开发 / 测试',
     'UI层、全屏适配、测试',
     'ConfigPanel配置面板、AudioManager音频、全屏DPI适配、系统测试用例编写与执行、文档撰写'],
]
for r, row_data in enumerate(data):
    for c, text in enumerate(row_data):
        table.rows[r + 1].cells[c].text = text
        for p in table.rows[r + 1].cells[c].paragraphs:
            for run in p.runs:
                run.font.size = Pt(9)
doc.add_paragraph()

doc.add_page_break()

# ════════════════════════════════════════════════════════════════
# 4  详细设计
# ════════════════════════════════════════════════════════════════
heading('4  详细设计', 1)

heading('4.1  系统架构设计', 2)
body('系统采用模块化架构，分为网络层、业务逻辑层和渲染层三层。')
body('网络层（NetworkManager / HostRegistry）：负责 UDP 收发、主机注册表维护、消息打包/解包。运行在独立线程中，避免阻塞主渲染循环。')
body('业务逻辑层（Fish / message）：负责鱼实体物理计算、跨屏传输判断、通信协议编解码。')
body('渲染层（Renderer / SpriteManager / BackgroundManager / ConfigPanel）：负责鱼精灵渲染、背景绘制、HUD 显示、配置面板交互。')

heading('4.2  通信协议设计', 2)
body('系统采用自定义二进制协议，基于 UDP 传输。所有消息统一包含 8 字节头部（类型1B + 发送者ID 1B + 时间戳4B + 负载长度2B），后接变长负载。')
body('消息类型共 9 种：HELLO(0x01) 用于发现握手，ACK(0x02) 响应握手，HEARTBEAT(0x03) 保活与精灵类型同步，TOPOLOGY(0x04) 拓扑信息广播，TRANSFER(0x05) 跨屏传输鱼数据，GOODBYE(0x06) 断联通知，SPRITE_PING(0x07) / SPRITE_REQ(0x08) / SPRITE_CHUNK(0x09) 用于精灵同步。')

heading('4.3  组网与拓扑管理', 2)
body('HostRegistry 维护一个以 "IP:port" 为键的主机注册表，每台主机同时记录自报 IP 和可达 IP（UDP 实际来源地址），以兼容多网卡环境。')
body('拓扑采用线性条带模型：所有主机按键的字典序排列，每台主机只与左右邻居交互。rebuild_topology() 在每个帧循环中调用，实时更新拓扑。')
body('组网流程：启动时广播 HELLO → 收到其他主机的 HELLO 后单播 ACK → 收到 ACK 后广播 TOPOLOGY。每 15 秒进行一次发现广播（携带所有已知主机信息），直到预期主机数达标后切换为纯单播。')
body('心跳机制：纯单播发送给已知主机，携带精灵类型信息（仅在类型变化时携带，避免冗余）。心跳匹配使用 UDP 实际来源地址而非自报 IP，以消除多网卡环境下的匹配失败。')

heading('4.4  跨屏传输机制', 2)
body('鱼触碰屏幕左右边界时触发传输：源端标记 fish.in_bridge = True，通过 TRANSFER 消息将鱼的完整状态（fish_id、坐标、方向、速度、大小、颜色、精灵类型）发送给邻居主机，邻居主机在屏幕外侧生成新鱼并滑入。')
body('源端鱼滑出屏幕 80 像素后移除，目标端鱼从屏幕外侧 80 像素处滑入，实现视觉上的无缝桥接。映射公式使用比例映射 fish.x = screen_w × (1 − src_x / src_w)，支持两端屏幕不同分辨率（窗口 800px ↔ 全屏 2560px）。')
body('桥接状态下的鱼增加了朝向感知的 bail-out 逻辑：只有在鱼面朝屏幕外侧且对应邻居不存在时才弹回，防止刚到达的鱼被误判。')

heading('4.5  精灵同步机制', 2)
body('心跳消息携带当前主机的精灵类型列表。接收方发现缺失类型时，发送 SPRITE_REQ 请求该类型的全部帧。发送方将每帧切分为 460 字节的 CHUNK，通过 SPRITE_CHUNK 分片传输。接收方由 SpriteSyncManager 重组完整 PNG 并写入本地精灵目录，随后触发全局精灵重扫描。')
body('精灵帧缓存：每条鱼维护一个 _scaled_cache 字典，以 (turn_state, anim_frame) 为键，缓存 smoothscale 后的 Surface，避免每帧重复缩放。')

doc.add_page_break()

# ════════════════════════════════════════════════════════════════
# 5  系统实现
# ════════════════════════════════════════════════════════════════
heading('5  系统实现', 1)

heading('5.1  关键模块实现', 2)
body('项目源码位于 src/ 目录，包含 11 个 Python 模块：')
body('• network.py — NetworkManager（UDP 收发、端口绑定、广播/单播）和 HostRegistry（主机注册表、拓扑重建、超时检测）。')
body('• message.py — 9 种消息类型的打包/解包函数，统一二进制帧头结构。')
body('• main.py — 主循环：事件处理、网络消息分发、鱼更新与跨屏传输、心跳与发现广播调度、渲染管线。')
body('• fish_entity.py — Fish 类：物理运动、屏幕弹跳、精灵动画帧、碰撞半径计算。')
body('• renderer.py — 鱼精灵绘制（含缩放缓存）、HUD 绘制（字体/Surface 缓存）。')
body('• sprite_manager.py — 精灵目录扫描、精灵帧加载与翻转、精灵导入。')
body('• sprite_sync.py — 网络精灵分片重组。')
body('• background_manager.py — 渐变/图片/视频三种背景模式。')
body('• audio_manager.py — 背景音乐循环播放与控制。')
body('• ui.py — 配置面板交互（鱼数量、速度、背景、全屏、精灵导入）。')
body('• config.py — INI 配置文件读写。')

heading('5.2  帧率优化历程', 2)
body('本项目在开发过程中遇到了严重的帧率持续下降问题，经过逐步排查和优化，最终实现了帧率稳定。以下是关键优化步骤：')

body('(1) 消除每帧字体创建：原 draw_hud() 每帧调用 pygame.font.SysFont() 创建新 Font 对象，SDL 底层 C 资源泄漏导致帧率逐步下降。改为模块级单例缓存，全生命周期只创建一次。')
body('(2) 消除每帧精灵缩放：原 draw_fish() 每帧对每条鱼调用 pygame.transform.smoothscale() 创建新 Surface。改为在 Fish 对象上维护 _scaled_cache 字典，按 (turn_state, anim_frame) 缓存已缩放 Surface。')
body('(3) 消除每帧 HUD Surface 创建：原 draw_hud() 每帧创建新的 HUD 背景 Surface 和 4 个文本 Surface。改为所有文本 Surface 仅在内容变化时重建，HUD 背景永久缓存，直接 blit 到屏幕。')
body('(4) 定时器精度修复：Windows 默认定时器精度 15.6ms，导致 clock.tick(30) 中 SDL_Delay 无法精确睡眠。调用 timeBeginPeriod(1) 将精度提升至 1ms。')
body('(5) 消除双重时钟源冲突：DOUBLEBUF + flip() 引入 GPU vsync(60Hz) 作为独立时钟源，与 clock.tick(30) 的 SDL_Delay 抢节奏。改为 clock.tick(60) 对齐 vsync，让 vsync 做主时钟源。')
body('(6) 心跳广播降频：原心跳每 3 秒向 10 个端口各发一次广播（每秒 3.3 次 sendto），WiFi 驱动发送队列堆积阻塞主线程。改为单端口广播 + 已知主机单播，最终改为纯单播。')
body('(7) 拆离主线程 sendto：所有网络发送操作（broadcast、send_known）移至网络监听线程执行，主线程仅通过设置共享变量触发，绝不调用阻塞的 sendto。')
body('(8) 过滤自收消息：广播发送后本机也会收到自己的广播，触发 HELLO→ACK→TOPOLOGY 级联处理，又引入主线程 sendto。在主循环中增加自收消息过滤（addr == (my_ip, my_port)），直接跳过。')

doc.add_page_break()

# ════════════════════════════════════════════════════════════════
# 6  系统测试
# ════════════════════════════════════════════════════════════════
heading('6  系统测试', 1)

heading('6.1  测试环境', 2)
body('• 测试机器 A（开发机）：Windows 11，1920×1080，集成显卡')
body('• 测试机器 B：Windows 11，1920×1080，独立显卡')
body('• 测试机器 C：Windows 11，2560×1600（150% DPI），独立显卡')
body('• 网络环境：同一路由器 2.4GHz WiFi 局域网')
body('• Python 3.13，pygame 2.6')

heading('6.2  功能测试用例', 2)

table = doc.add_table(rows=1, cols=6)
table.style = 'Table Grid'
for i, h in enumerate(['编号', '测试项', '操作步骤', '预期效果', '实际效果', '结果']):
    cell = table.rows[0].cells[i]
    cell.text = h
    for p in cell.paragraphs:
        for run in p.runs:
            run.bold = True
            run.font.size = Pt(9)

test_cases = [
    ['T01', '双机组网\n(A先)',
     'A启动→B启动',
     '双方host数=2，\n#0/#1正确',
     '双方host数=2，\n#0/#1正确',
     '✓'],
    ['T02', '双机组网\n(B先)',
     'B启动→A启动',
     '双方host数=2',
     'A等15秒发现广播\n后组网成功',
     '✓'],
    ['T03', '三机组网\n(信号全覆盖)',
     'A→B→C依次启动',
     '三方host数=3，\n#0/#1/#2线性排列',
     '三方host数=3，\n#0/#1/#2正确',
     '✓'],
    ['T04', '三机组网\n(拓扑中转)',
     'A↔B↔C（A-C不通）',
     'B的TOPOLOGY广播\n让A/C互发现',
     'A/C通过B的\nTOPOLOGY互相发现',
     '✓'],
    ['T05', '跨屏传输\n(窗口→窗口)',
     '鱼游到屏幕边缘',
     '鱼从源屏消失\n从目标屏出现',
     '鱼平滑过渡，\nbridge效果正确',
     '✓'],
    ['T06', '跨屏传输\n(窗口↔全屏)',
     '一窗口一全屏，\n鱼跨屏',
     '鱼正确映射，\n不同分辨率对齐',
     '比例映射正确，\n鱼从正确位置出现',
     '✓'],
    ['T07', '断联检测',
     '关闭一台主机窗口',
     '其余主机host数\n在10秒内更新',
     'GOODBYE即时更新\n或心跳超时更新',
     '✓'],
    ['T08', '精灵同步',
     '一台导入新精灵',
     '其他主机自动\n同步新精灵',
     '心跳触发请求，\nCHUNK分片接收',
     '✓'],
    ['T09', '全屏显示\n(普通DPI)',
     '按F切换全屏',
     '画面填满屏幕\n无黑边',
     '1920×1080填满',
     '✓'],
    ['T10', '全屏显示\n(高DPI)',
     '2560×1600/150%\n按F切换全屏',
     '画面填满屏幕\n无黑边',
     'SetProcessDpiAwareness\n后全屏填满',
     '✓'],
    ['T11', '帧率稳定性\n(单机)',
     '单机运行10分钟',
     '帧率维持60fps',
     '帧率稳定60fps',
     '✓'],
    ['T12', '帧率稳定性\n(组网运行)',
     '三机组网运行\n10分钟',
     '帧率维持60fps',
     '纯单播后稳定60fps\n组网完成前偶有波动',
     '✓'],
    ['T13', '自定义组网数',
     '启动输入2/3',
     '达到目标数后\n停止发现广播',
     'host_count≥expected\n时广播停止',
     '✓'],
]

for tc in test_cases:
    row = table.add_row()
    for i, text in enumerate(tc):
        row.cells[i].text = text
        for p in row.cells[i].paragraphs:
            for run in p.runs:
                run.font.size = Pt(8)

doc.add_paragraph()

heading('6.3  性能测试', 2)
body('性能优化的核心指标是帧率稳定性。下表记录了优化前后帧率随时间变化的情况：')

table = doc.add_table(rows=5, cols=4)
table.style = 'Table Grid'
for i, h in enumerate(['运行时长', '优化前帧率', '优化后帧率(单机)', '优化后帧率(三机组网)']):
    table.rows[0].cells[i].text = h
    for p in table.rows[0].cells[i].paragraphs:
        for run in p.runs:
            run.bold = True
            run.font.size = Pt(10)
perf_data = [
    ['0分钟', '60fps', '60fps', '60fps'],
    ['1分钟', '30fps', '60fps', '60fps'],
    ['5分钟', '12fps', '60fps', '58fps'],
    ['10分钟', '3-5fps', '60fps', '58fps'],
]
for r, row_data in enumerate(perf_data):
    for c, text in enumerate(row_data):
        table.rows[r + 1].cells[c].text = text
        for p in table.rows[r + 1].cells[c].paragraphs:
            for run in p.runs:
                run.font.size = Pt(10)

doc.add_paragraph()

doc.add_page_break()

# ════════════════════════════════════════════════════════════════
# 7  总结
# ════════════════════════════════════════════════════════════════
heading('7  总结', 1)

heading('7.1  遇到的困难与解决方法', 2)

body('困难一：帧率持续下降至个位数。这是本项目遇到的最棘手的问题，经历十余轮排查才最终解决。最初怀疑是渲染路径的 Surface 分配泄漏，经过字体缓存、精灵缩放缓存、HUD 缓存等优化后无效；接着怀疑 pygame 定时器精度，提升 Windows timer 分辨率并消除 DOUBLEBUF vsync 冲突后仍无效。最终通过逐模块二分排除法定位到 net.broadcast() ——每 3 秒向 10 个端口各发一次 UDP 广播，WiFi 驱动发送队列逐渐堆积导致 sendto 阻塞主线程。解决方案为：心跳改为纯单播，发现广播降频至 15 秒且组网完成后停止，所有 sendto 移至网络线程执行，主线程过滤自收消息从而完全不触发 sendto。')
body('困难二：三台电脑组网拓扑错误。在 WiFi 信号不完全覆盖的场景下（A↔B↔C 但 A↛C），A 和 C 都排到 #0，无法形成正确的线性拓扑。根因在于 TOPOLOGY 消息原来只携带 (host_id, position) 而无地址信息，中间主机 B 无法帮 A 和 C 互相引荐。解决方案：将 TOPOLOGY 消息扩展为携带每个主机的可达 IP 和端口，发现广播从 HELLO 升级为携带全部已知主机的 TOPOLOGY，使 B 的广播能让 A 和 C 互相发现。')
body('困难三：高 DPI 屏幕全屏有黑边。2560×1600 分辨率 150% 缩放的屏幕，pygame 全屏后左右有黑边。根因缺少 Windows DPI 感知声明，Windows 向 SDL 谎报逻辑分辨率(1707×1067)而非物理分辨率。解决方案：在 pygame.init() 之前调用 SetProcessDpiAwareness(2) 声明 Per-Monitor DPI 感知，同时将 set_mode 分辨率参数改为 (0,0) 让 SDL 自行获取。')
body('困难四：不同电脑的 font 兼容性问题。pygame 2.6.1 在部分系统上 SysFont 扫描损坏的字体注册表项时抛出 TypeError 崩溃。解决方案：编写 safe_font() 包装函数，SysFont 失败时回退到 pygame.font.Font(None, size) 默认字体。')

heading('7.2  不足与展望', 2)

body('本项目的不足：')
body('(1) 拓扑仅支持线性条带模型。主机左右各只有一个邻居，鱼只能向左或向右跨屏，无法支持更复杂的二维或环形拓扑。未来可扩展为网状拓扑或环形拓扑，实现更灵活的跨屏路径。')
body('(2) 缺乏可靠传输保证。UDP 无连接无重传，TRANSFER 消息依赖连续发送两次来提高送达率，但无法保证 100% 送达。未来可在应用层实现简单的 ACK 重传机制。')
body('(3) 依赖同一局域网。所有主机必须在同一子网内，无法跨子网通信。未来可引入 NAT 穿透或中继服务器。')
body('(4) 配置面板交互方式单一。目前仅支持鼠标点击，无快捷键提示和键盘导航。未来可增加完整的键盘操作支持。')
body('(5) 缺少日志和诊断工具。调试组网问题需逐台查看 HUD，没有集中的日志记录。未来可增加日志模块，记录关键网络事件。')

body('展望：本项目实现了一个去中心化的局域网多屏联动游鱼动画系统，具备自动组网、跨屏传输、断联检测、精灵同步等功能。通过深入的性能优化实现了帧率稳定运行。未来可继续完善拓扑灵活性、通信可靠性和用户体验，使其成为一个更成熟的分布式屏幕联动引擎。')

# ── save ──
out_path = os.path.join(os.path.dirname(__file__),
                        '局域网多屏联动游鱼动画系统_设计报告.docx')
doc.save(out_path)
print(f'Saved to: {out_path}')
