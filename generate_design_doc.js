const {
  Document, Packer, Paragraph, TextRun, HeadingLevel,
  Table, TableRow, TableCell, WidthType, BorderStyle,
  AlignmentType, PageOrientation
} = require('docx');
const fs = require('fs');

// ── helpers ──
const para = (text, opts = {}) => new Paragraph({
  children: [new TextRun({ text, ...opts })],
  spacing: { line: 360, lineRule: "auto" },
});

const heading = (level, text) => new Paragraph({
  children: [new TextRun({ text, bold: true })],
  heading: level,
  spacing: { before: 240, after: 120 },
});

const bulletItem = (text) => new Paragraph({
  children: [new TextRun({ text })],
  bullet: { level: 0 },
  spacing: { line: 360, lineRule: "auto" },
});

const indentItem = (text) => new Paragraph({
  children: [new TextRun({ text })],
  indent: { left: 720 },
  spacing: { line: 360, lineRule: "auto" },
});

const emptyLine = () => new Paragraph({ children: [] });

// ── document sections ──
let children = [];

// ── 封面信息 ──
children.push(new Paragraph({
  children: [new TextRun({ text: "重庆交通大学信息科学与工程学院", size: 28, bold: true })],
  alignment: AlignmentType.CENTER,
  spacing: { after: 400 },
}));

children.push(new Paragraph({
  children: [new TextRun({ text: "集中实践环节阶段检查", size: 24 })],
  alignment: AlignmentType.CENTER,
  spacing: { after: 600 },
}));

children.push(emptyLine());
children.push(emptyLine());

children.push(new Paragraph({
  children: [new TextRun({ text: "题    目：", bold: true, size: 24 }), new TextRun({ text: "局域网多屏联动游鱼动画系统", size: 24 })],
  spacing: { after: 300 },
}));

children.push(new Paragraph({
  children: [new TextRun({ text: "文 档 名：", bold: true, size: 24 }), new TextRun({ text: "初步设计文档", size: 24 })],
  spacing: { after: 300 },
}));

children.push(new Paragraph({
  children: [new TextRun({ text: "课程名称：", bold: true, size: 24 }), new TextRun({ text: "计算思维综合实践II", size: 24 })],
  spacing: { after: 300 },
}));

children.push(new Paragraph({
  children: [new TextRun({ text: "专业班级：", bold: true, size: 24 }), new TextRun({ text: "计算机2023级  班", size: 24 })],
  spacing: { after: 300 },
}));

children.push(new Paragraph({
  children: [new TextRun({ text: "学    号：", bold: true, size: 24 })],
  spacing: { after: 300 },
}));

children.push(new Paragraph({
  children: [new TextRun({ text: "姓    名：", bold: true, size: 24 })],
  spacing: { after: 300 },
}));

children.push(new Paragraph({
  children: [new TextRun({ text: "指导教师：", bold: true, size: 24 }), new TextRun({ text: "李益才", size: 24 })],
  spacing: { after: 300 },
}));

children.push(new Paragraph({
  children: [new TextRun({ text: "2026年6月", size: 24 })],
  alignment: AlignmentType.RIGHT,
  spacing: { before: 600 },
}));

// ── 分割线 ──
children.push(new Paragraph({
  children: [new TextRun({ text: "局域网多屏联动游鱼动画系统", size: 28, bold: true })],
  alignment: AlignmentType.CENTER,
  spacing: { before: 600, after: 400 },
}));

children.push(new Paragraph({
  children: [new TextRun({ text: "初步设计文档", size: 28, bold: true })],
  alignment: AlignmentType.CENTER,
  spacing: { after: 600 },
}));

// ── 一、系统功能设计 ──
children.push(heading(HeadingLevel.HEADING_1, "一、系统功能设计"));

// 1. 系统功能模块图
children.push(heading(HeadingLevel.HEADING_2, "1、系统功能模块图"));

children.push(para(""));
children.push(para("系统功能模块图（Mermaid）：", { run: { bold: true } }));
children.push(para(""));
children.push(para("graph TB", { run: { font: "Courier New", size: 18 } }));
children.push(para("  subgraph 系统主模块", { run: { font: "Courier New", size: 18 } }));
children.push(para("    MAIN[主循环模块<br/>main.py]", { run: { font: "Courier New", size: 18 } }));
children.push(para("  end", { run: { font: "Courier New", size: 18 } }));
children.push(para("  subgraph 功能子模块", { run: { font: "Courier New", size: 18 } }));
children.push(para("    FISH[鱼群管理模块<br/>fish_entity.py]", { run: { font: "Courier New", size: 18 } }));
children.push(para("    RENDER[渲染模块<br/>renderer.py]", { run: { font: "Courier New", size: 18 } }));
children.push(para("    NETWORK[网络通信模块<br/>network.py]", { run: { font: "Courier New", size: 18 } }));
children.push(para("    AUDIO[音效模块<br/>audio_manager.py]", { run: { font: "Courier New", size: 18 } }));
children.push(para("    CONFIG[配置模块<br/>config.py]", { run: { font: "Courier New", size: 18 } }));
children.push(para("    UI[界面模块<br/>ui.py]", { run: { font: "Courier New", size: 18 } }));
children.push(para("  end", { run: { font: "Courier New", size: 18 } }));
children.push(para("  subgraph 消息子模块", { run: { font: "Courier New", size: 18 } }));
children.push(para("    MSG[消息处理模块<br/>message.py]", { run: { font: "Courier New", size: 18 } }));
children.push(para("  end", { run: { font: "Courier New", size: 18 } }));
children.push(para("  MAIN --> FISH", { run: { font: "Courier New", size: 18 } }));
children.push(para("  MAIN --> RENDER", { run: { font: "Courier New", size: 18 } }));
children.push(para("  MAIN --> NETWORK", { run: { font: "Courier New", size: 18 } }));
children.push(para("  MAIN --> AUDIO", { run: { font: "Courier New", size: 18 } }));
children.push(para("  MAIN --> CONFIG", { run: { font: "Courier New", size: 18 } }));
children.push(para("  MAIN --> UI", { run: { font: "Courier New", size: 18 } }));
children.push(para("  NETWORK --> MSG", { run: { font: "Courier New", size: 18 } }));

children.push(para(""));
children.push(para("系统功能模块说明：", { run: { bold: true } }));

// 系统功能描述
children.push(heading(HeadingLevel.HEADING_2, "2、系统功能描述"));

children.push(para("【1】主循环模块（main.py）", { run: { bold: true } }));
children.push(indentItem("功能：系统的核心入口，负责协调各模块工作，管理主循环流程。"));
children.push(indentItem("职责：Pygame初始化、主循环控制（事件处理→鱼更新→边界检测→跨屏通信→渲染）、键盘鼠标事件处理、程序退出管理。"));
children.push(emptyLine());

children.push(para("【2】鱼群管理模块（fish_entity.py）", { run: { bold: true } }));
children.push(indentItem("功能：管理单条鱼的属性和行为。"));
children.push(indentItem("职责：Fish类定义（ID、位置、方向、速度、大小、颜色等属性）、位置更新、边界反弹、颜色随机生成、鱼ID生成（主机ID+计数器）。"));
children.push(emptyLine());

children.push(para("【3】渲染模块（renderer.py）", { run: { bold: true } }));
children.push(indentItem("功能：封装Pygame渲染函数，绘制所有视觉元素。"));
children.push(indentItem("职责：深蓝色渐变背景绘制、鱼精灵绘制（身体椭圆+尾巴三角+眼睛）、鱼群批量绘制、HUD信息面板绘制（FPS、鱼数量、主机数量、自身ID）。"));
children.push(emptyLine());

children.push(para("【4】网络通信模块（network.py）", { run: { bold: true } }));
children.push(indentItem("功能：实现P2P网络通信，包括主机发现、消息传输、拓扑管理。"));
children.push(indentItem("职责：NetworkManager类（Socket管理、UDP广播/单播、监听线程）、HostRegistry类（主机列表维护、心跳检测、拓扑排序、邻居管理）。"));
children.push(emptyLine());

children.push(para("【5】消息处理模块（message.py）", { run: { bold: true } }));
children.push(indentItem("功能：定义和管理6种消息类型的序列化/反序列化。"));
children.push(indentItem("职责：HELLO（上线请求）、ACK（上线响应）、HEARTBEAT（心跳）、TOPOLOGY（拓扑更新）、TRANSFER（鱼状态传输）、GOODBYE（下线通知），使用struct二进制编码。"));
children.push(emptyLine());

children.push(para("【6】音效模块（audio_manager.py）", { run: { bold: true } }));
children.push(indentItem("功能：管理水流背景音效的播放和控制。"));
children.push(indentItem("职责：pygame.mixer封装、音频加载、循环播放、暂停/恢复、音量控制、启用/禁用切换。"));
children.push(emptyLine());

children.push(para("【7】配置模块（config.py）", { run: { bold: true } }));
children.push(indentItem("功能：管理系统配置，读取和保存config.ini。"));
children.push(indentItem("职责：配置项定义（窗口尺寸、鱼数量、速度、端口、心跳参数、音量）、配置读取（load函数）、配置保存（save函数）、默认配置初始化。"));
children.push(emptyLine());

children.push(para("【8】界面模块（ui.py）", { run: { bold: true } }));
children.push(indentItem("功能：实现配置面板UI，支持用户交互。"));
children.push(indentItem("职责：ConfigPanel类（面板显示/隐藏、鼠标点击处理、状态更新）、Button类（按钮绘制和交互）、滑块控制（鱼数量±、速度±）、开关控制（跨屏联动、音效）、操作按钮（暂停、重置）。"));

children.push(para(""));
children.push(para("核心功能流程：", { run: { bold: true } }));
children.push(bulletItem("初始化阶段：Pygame初始化 → 配置加载 → UDP Socket创建 → 网络线程启动 → HELLO广播 → 组网完成"));
children.push(bulletItem("主循环阶段：事件处理 → 鱼位置更新 → 边界检测 → 跨屏传输 → 队列消息处理 → 渲染画面 → 帧率控制"));
children.push(bulletItem("退出阶段：GOODBYE广播 → 网络线程停止 → Socket关闭 → 配置保存 → 程序退出"));

// ── 二、系统数据模型设计 ──
children.push(heading(HeadingLevel.HEADING_1, "二、系统数据模型设计"));

// 1. 类模型
children.push(heading(HeadingLevel.HEADING_2, "1、类模型"));

children.push(para(""));
children.push(para("类模型图（UML类图，Mermaid）：", { run: { bold: true } }));
children.push(para(""));
children.push(para("classDiagram", { run: { font: "Courier New", size: 18 } }));
children.push(para("  class Fish", { run: { font: "Courier New", size: 18 } }));
children.push(para("  Fish : +int fish_id", { run: { font: "Courier New", size: 18 } }));
children.push(para("  Fish : +float x, y", { run: { font: "Courier New", size: 18 } }));
children.push(para("  Fish : +float direction", { run: { font: "Courier New", size: 18 } }));
children.push(para("  Fish : +float speed", { run: { font: "Courier New", size: 18 } }));
children.push(para("  Fish : +float size", { run: { font: "Courier New", size: 18 } }));
children.push(para("  Fish : +tuple color", { run: { font: "Courier New", size: 18 } }));
children.push(para("  Fish : +int host_id", { run: { font: "Courier New", size: 18 } }));
children.push(para("  Fish : +float wag_phase", { run: { font: "Courier New", size: 18 } }));
children.push(para("  Fish : +float transfer_cooldown", { run: { font: "Courier New", size: 18 } }));
children.push(para("  Fish : +update(dt, speed_multiplier)", { run: { font: "Courier New", size: 18 } }));
children.push(para("  Fish : +bounce(screen_w, screen_h, margin)", { run: { font: "Courier New", size: 18 } }));

children.push(para(""));
children.push(para("  class HostInfo", { run: { font: "Courier New", size: 18 } }));
children.push(para("  HostInfo : +str hostname", { run: { font: "Courier New", size: 18 } }));
children.push(para("  HostInfo : +str ip", { run: { font: "Courier New", size: 18 } }));
children.push(para("  HostInfo : +int port", { run: { font: "Courier New", size: 18 } }));
children.push(para("  HostInfo : +int host_id", { run: { font: "Courier New", size: 18 } }));
children.push(para("  HostInfo : +int position", { run: { font: "Courier New", size: 18 } }));
children.push(para("  HostInfo : +float last_heartbeat", { run: { font: "Courier New", size: 18 } }));
children.push(para("  HostInfo : +make_key(ip, port)", { run: { font: "Courier New", size: 18 } }));
children.push(para("  HostInfo : +key()", { run: { font: "Courier New", size: 18 } }));

children.push(para(""));
children.push(para("  class HostRegistry", { run: { font: "Courier New", size: 18 } }));
children.push(para("  HostRegistry : +dict hosts", { run: { font: "Courier New", size: 18 } }));
children.push(para("  HostRegistry : +str my_hostname, my_ip", { run: { font: "Courier New", size: 18 } }));
children.push(para("  HostRegistry : +int my_port, my_id", { run: { font: "Courier New", size: 18 } }));
children.push(para("  HostRegistry : +str left, right", { run: { font: "Courier New", size: 18 } }));
children.push(para("  HostRegistry : +add_or_update(hostname, ip, port)", { run: { font: "Courier New", size: 18 } }));
children.push(para("  HostRegistry : +heartbeat(ip, port)", { run: { font: "Courier New", size: 18 } }));
children.push(para("  HostRegistry : +remove_by_key(key)", { run: { font: "Courier New", size: 18 } }));
children.push(para("  HostRegistry : +check_timeout(timeout)", { run: { font: "Courier New", size: 18 } }));
children.push(para("  HostRegistry : +rebuild_topology()", { run: { font: "Courier New", size: 18 } }));

children.push(para(""));
children.push(para("  class NetworkManager", { run: { font: "Courier New", size: 18 } }));
children.push(para("  NetworkManager : +socket sock", { run: { font: "Courier New", size: 18 } }));
children.push(para("  NetworkManager : +int port", { run: { font: "Courier New", size: 18 } }));
children.push(para("  NetworkManager : +bool running", { run: { font: "Courier New", size: 18 } }));
children.push(para("  NetworkManager : +Thread thread", { run: { font: "Courier New", size: 18 } }));
children.push(para("  NetworkManager : +start_listen(queue)", { run: { font: "Courier New", size: 18 } }));
children.push(para("  NetworkManager : +broadcast(data)", { run: { font: "Courier New", size: 18 } }));
children.push(para("  NetworkManager : +send(ip, port, data)", { run: { font: "Courier New", size: 18 } }));
children.push(para("  NetworkManager : +shutdown()", { run: { font: "Courier New", size: 18 } }));

children.push(para(""));
children.push(para("  class AudioManager", { run: { font: "Courier New", size: 18 } }));
children.push(para("  AudioManager : +bool enabled", { run: { font: "Courier New", size: 18 } }));
children.push(para("  AudioManager : +float volume", { run: { font: "Courier New", size: 18 } }));
children.push(para("  AudioManager : +Sound sound", { run: { font: "Courier New", size: 18 } }));
children.push(para("  AudioManager : +Channel channel", { run: { font: "Courier New", size: 18 } }));
children.push(para("  AudioManager : +play()", { run: { font: "Courier New", size: 18 } }));
children.push(para("  AudioManager : +toggle()", { run: { font: "Courier New", size: 18 } }));
children.push(para("  AudioManager : +set_volume(v)", { run: { font: "Courier New", size: 18 } }));
children.push(para("  AudioManager : +stop()", { run: { font: "Courier New", size: 18 } }));

children.push(para(""));
children.push(para("  class Button", { run: { font: "Courier New", size: 18 } }));
children.push(para("  Button : +Rect rect", { run: { font: "Courier New", size: 18 } }));
children.push(para("  Button : +str text", { run: { font: "Courier New", size: 18 } }));
children.push(para("  Button : +tuple color, text_color", { run: { font: "Courier New", size: 18 } }));
children.push(para("  Button : +bool hovered", { run: { font: "Courier New", size: 18 } }));
children.push(para("  Button : +update(mx, my)", { run: { font: "Courier New", size: 18 } }));
children.push(para("  Button : +draw(screen, font)", { run: { font: "Courier New", size: 18 } }));
children.push(para("  Button : +clicked()", { run: { font: "Courier New", size: 18 } }));

children.push(para(""));
children.push(para("  class ConfigPanel", { run: { font: "Courier New", size: 18 } }));
children.push(para("  ConfigPanel : +bool visible", { run: { font: "Courier New", size: 18 } }));
children.push(para("  ConfigPanel : +int screen_w, screen_h", { run: { font: "Courier New", size: 18 } }));
children.push(para("  ConfigPanel : +int fish_count", { run: { font: "Courier New", size: 18 } }));
children.push(para("  ConfigPanel : +float speed_mult", { run: { font: "Courier New", size: 18 } }));
children.push(para("  ConfigPanel : +bool cross_screen", { run: { font: "Courier New", size: 18 } }));
children.push(para("  ConfigPanel : +toggle()", { run: { font: "Courier New", size: 18 } }));
children.push(para("  ConfigPanel : +handle_click()", { run: { font: "Courier New", size: 18 } }));
children.push(para("  ConfigPanel : +draw(screen, ...)", { run: { font: "Courier New", size: 18 } }));

children.push(para(""));
children.push(para('  HostRegistry "1" o-- "*" HostInfo : 包含'));
children.push(para('  NetworkManager "1" --> "1" HostRegistry : 使用'));

children.push(para(""));
children.push(para("类模型说明：", { run: { bold: true } }));
children.push(indentItem("Fish类：核心数据类，表示单条鱼的实体，包含所有属性和基本行为方法（update、bounce）。"));
children.push(indentItem("HostInfo类：网络数据类，表示网络中其他主机的信息，用于主机发现和心跳管理。"));
children.push(indentItem("HostRegistry类：主机管理类，维护所有主机列表，管理拓扑关系（左右邻居），提供心跳检测和超时处理。"));
children.push(indentItem("NetworkManager类：网络管理类，封装Socket操作，提供广播、单播、消息接收等功能，启动和管理监听线程。"));
children.push(indentItem("AudioManager类：音频数据类，管理音效的播放状态和控制接口。"));
children.push(indentItem("Button类：UI控件类，表示可点击按钮，包含绘制和交互方法。"));
children.push(indentItem("ConfigPanel类：UI控件类，表示配置面板容器，管理多个Button组件，提供参数配置界面。"));

children.push(para(""));
children.push(para("类间关系说明：", { run: { bold: true } }));
children.push(bulletItem("聚合关系：HostRegistry聚合多个HostInfo对象，表示一对多关系"));
children.push(bulletItem("依赖关系：NetworkManager依赖HostRegistry进行主机管理"));
children.push(bulletItem("无UI类继承：本数据模型仅关注业务数据，不包含UI类的继承关系"));

// 2. 类体结构
children.push(heading(HeadingLevel.HEADING_2, "2、类体结构"));

children.push(para("【1】Fish类定义（fish_entity.py）", { run: { bold: true } }));
children.push(para(""));
children.push(para("class Fish:", { run: { font: "Courier New", size: 20 } }));
children.push(para("    \"\"\"鱼实体类：管理单条鱼的属性和行为\"\"\"", { run: { font: "Courier New", size: 20 } }));
children.push(para("    _id_counter: int = 0  # 类级别计数器", { run: { font: "Courier New", size: 20 } }));
children.push(para("", { run: { font: "Courier New", size: 20 } }));
children.push(para("    def __init__(self, host_id: int, x: float = None, y: float = None) -> None:", { run: { font: "Courier New", size: 20 } }));
children.push(para("        self.fish_id: int = (host_id << 8) | (Fish._id_counter & 0xFF)", { run: { font: "Courier New", size: 20 } }));
children.push(para("        self.x: float = x or random.uniform(100, 700)", { run: { font: "Courier New", size: 20 } }));
children.push(para("        self.y: float = y or random.uniform(100, 500)", { run: { font: "Courier New", size: 20 } }));
children.push(para("        self.direction: float = random.uniform(0, 2 * math.pi)", { run: { font: "Courier New", size: 20 } }));
children.push(para("        self.speed: float = random.uniform(60, 160)", { run: { font: "Courier New", size: 20 } }));
children.push(para("        self.size: float = random.uniform(0.6, 1.4)", { run: { font: "Courier New", size: 20 } }));
children.push(para("        self.color: tuple = self._random_color()", { run: { font: "Courier New", size: 20 } }));
children.push(para("        self.host_id: int = host_id", { run: { font: "Courier New", size: 20 } }));
children.push(para("        self.wag_phase: float = random.uniform(0, 2 * math.pi)", { run: { font: "Courier New", size: 20 } }));
children.push(para("        self.transfer_cooldown: float = 0.0", { run: { font: "Courier New", size: 20 } }));
children.push(para("", { run: { font: "Courier New", size: 20 } }));
children.push(para("    def _random_color(self) -> tuple:", { run: { font: "Courier New", size: 20 } }));
children.push(para("        \"\"\"随机生成鱼的颜色（HSV转RGB）\"\"\"", { run: { font: "Courier New", size: 20 } }));
children.push(para("        ...", { run: { font: "Courier New", size: 20 } }));
children.push(para("", { run: { font: "Courier New", size: 20 } }));
children.push(para("    def update(self, dt: float, speed_multiplier: float = 1.0) -> None:", { run: { font: "Courier New", size: 20 } }));
children.push(para("        \"\"\"更新鱼的位置和动画状态\"\"\"", { run: { font: "Courier New", size: 20 } }));
children.push(para("        ...", { run: { font: "Courier New", size: 20 } }));
children.push(para("", { run: { font: "Courier New", size: 20 } }));
children.push(para("    def bounce(self, screen_w: int, screen_h: int, margin: int = 20) -> bool:", { run: { font: "Courier New", size: 20 } }));
children.push(para("        \"\"\"边界反弹处理\"\"\"", { run: { font: "Courier New", size: 20 } }));
children.push(para("        ...", { run: { font: "Courier New", size: 20 } }));

children.push(para(""));
children.push(para("【2】HostInfo类定义（network.py）", { run: { bold: true } }));
children.push(para(""));
children.push(para("class HostInfo:", { run: { font: "Courier New", size: 20 } }));
children.push(para("    \"\"\"主机信息类：存储网络中主机的基本信息\"\"\"", { run: { font: "Courier New", size: 20 } }));
children.push(para("", { run: { font: "Courier New", size: 20 } }));
children.push(para("    def __init__(self, hostname: str, ip: str, port: int) -> None:", { run: { font: "Courier New", size: 20 } }));
children.push(para("        self.hostname: str = hostname", { run: { font: "Courier New", size: 20 } }));
children.push(para("        self.ip: str = ip", { run: { font: "Courier New", size: 20 } }));
children.push(para("        self.port: int = port", { run: { font: "Courier New", size: 20 } }));
children.push(para("        self.host_id: int = 0", { run: { font: "Courier New", size: 20 } }));
children.push(para("        self.position: int = 0", { run: { font: "Courier New", size: 20 } }));
children.push(para("        self.last_heartbeat: float = time.time()", { run: { font: "Courier New", size: 20 } }));
children.push(para("", { run: { font: "Courier New", size: 20 } }));
children.push(para("    @staticmethod", { run: { font: "Courier New", size: 20 } }));
children.push(para("    def make_key(ip: str, port: int) -> str:", { run: { font: "Courier New", size: 20 } }));
children.push(para("        \"\"\"生成主机唯一标识键\"\"\"", { run: { font: "Courier New", size: 20 } }));
children.push(para("        ...", { run: { font: "Courier New", size: 20 } }));

children.push(para(""));
children.push(para("【3】HostRegistry类定义（network.py）", { run: { bold: true } }));
children.push(para(""));
children.push(para("class HostRegistry:", { run: { font: "Courier New", size: 20 } }));
children.push(para("    \"\"\"主机注册表类：管理所有主机的注册和拓扑关系\"\"\"", { run: { font: "Courier New", size: 20 } }));
children.push(para("", { run: { font: "Courier New", size: 20 } }));
children.push(para("    def __init__(self, port: int) -> None:", { run: { font: "Courier New", size: 20 } }));
children.push(para("        self.hosts: dict = {}  # \"ip:port\" -> HostInfo", { run: { font: "Courier New", size: 20 } }));
children.push(para("        self.my_hostname: str = socket.gethostname()", { run: { font: "Courier New", size: 20 } }));
children.push(para("        self.my_ip: str = self._get_my_ip()", { run: { font: "Courier New", size: 20 } }));
children.push(para("        self.my_port: int = port", { run: { font: "Courier New", size: 20 } }));
children.push(para("        self.my_id: int = 0", { run: { font: "Courier New", size: 20 } }));
children.push(para("        self.left: str = None  # 左邻居键", { run: { font: "Courier New", size: 20 } }));
children.push(para("        self.right: str = None  # 右邻居键", { run: { font: "Courier New", size: 20 } }));
children.push(para("", { run: { font: "Courier New", size: 20 } }));
children.push(para("    def add_or_update(self, hostname: str, ip: str, port: int) -> None:", { run: { font: "Courier New", size: 20 } }));
children.push(para("        \"\"\"添加或更新主机信息\"\"\"", { run: { font: "Courier New", size: 20 } }));
children.push(para("        ...", { run: { font: "Courier New", size: 20 } }));
children.push(para("", { run: { font: "Courier New", size: 20 } }));
children.push(para("    def heartbeat(self, ip: str, port: int) -> None:", { run: { font: "Courier New", size: 20 } }));
children.push(para("        \"\"\"更新主机心跳时间\"\"\"", { run: { font: "Courier New", size: 20 } }));
children.push(para("        ...", { run: { font: "Courier New", size: 20 } }));
children.push(para("", { run: { font: "Courier New", size: 20 } }));
children.push(para("    def rebuild_topology(self) -> None:", { run: { font: "Courier New", size: 20 } }));
children.push(para("        \"\"\"重新构建网络拓扑\"\"\"", { run: { font: "Courier New", size: 20 } }));
children.push(para("        ...", { run: { font: "Courier New", size: 20 } }));

children.push(para(""));
children.push(para("【4】NetworkManager类定义（network.py）", { run: { bold: true } }));
children.push(para(""));
children.push(para("class NetworkManager:", { run: { font: "Courier New", size: 20 } }));
children.push(para("    \"\"\"网络管理器类：封装Socket操作和网络通信\"\"\"", { run: { font: "Courier New", size: 20 } }));
children.push(para("", { run: { font: "Courier New", size: 20 } }));
children.push(para("    def __init__(self, start_port: int = 6000) -> None:", { run: { font: "Courier New", size: 20 } }));
children.push(para("        self.sock: socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)", { run: { font: "Courier New", size: 20 } }));
children.push(para("        self.port: int = self._bind(start_port)", { run: { font: "Courier New", size: 20 } }));
children.push(para("        self.running: bool = False", { run: { font: "Courier New", size: 20 } }));
children.push(para("        self.thread: threading.Thread = None", { run: { font: "Courier New", size: 20 } }));
children.push(para("", { run: { font: "Courier New", size: 20 } }));
children.push(para("    def start_listen(self, queue: Queue) -> None:", { run: { font: "Courier New", size: 20 } }));
children.push(para("        \"\"\"启动网络监听线程\"\"\"", { run: { font: "Courier New", size: 20 } }));
children.push(para("        ...", { run: { font: "Courier New", size: 20 } }));
children.push(para("", { run: { font: "Courier New", size: 20 } }));
children.push(para("    def broadcast(self, data: bytes) -> None:", { run: { font: "Courier New", size: 20 } }));
children.push(para("        \"\"\"UDP广播消息\"\"\"", { run: { font: "Courier New", size: 20 } }));
children.push(para("        ...", { run: { font: "Courier New", size: 20 } }));
children.push(para("", { run: { font: "Courier New", size: 20 } }));
children.push(para("    def send(self, ip: str, port: int, data: bytes) -> None:", { run: { font: "Courier New", size: 20 } }));
children.push(para("        \"\"\"UDP单播消息\"\"\"", { run: { font: "Courier New", size: 20 } }));
children.push(para("        ...", { run: { font: "Courier New", size: 20 } }));

children.push(para(""));
children.push(para("【5】AudioManager类定义（audio_manager.py）", { run: { bold: true } }));
children.push(para(""));
children.push(para("class AudioManager:", { run: { font: "Courier New", size: 20 } }));
children.push(para("    \"\"\"音频管理器类：管理音效播放和控制\"\"\"", { run: { font: "Courier New", size: 20 } }));
children.push(para("", { run: { font: "Courier New", size: 20 } }));
children.push(para("    def __init__(self, volume: float = 0.5) -> None:", { run: { font: "Courier New", size: 20 } }));
children.push(para("        self.enabled: bool = False", { run: { font: "Courier New", size: 20 } }));
children.push(para("        self.volume: float = volume", { run: { font: "Courier New", size: 20 } }));
children.push(para("        self.sound: pygame.mixer.Sound = None", { run: { font: "Courier New", size: 20 } }));
children.push(para("        self.channel: pygame.mixer.Channel = None", { run: { font: "Courier New", size: 20 } }));
children.push(para("", { run: { font: "Courier New", size: 20 } }));
children.push(para("    def play(self) -> None:", { run: { font: "Courier New", size: 20 } }));
children.push(para("        \"\"\"开始播放音效\"\"\"", { run: { font: "Courier New", size: 20 } }));
children.push(para("        ...", { run: { font: "Courier New", size: 20 } }));
children.push(para("", { run: { font: "Courier New", size: 20 } }));
children.push(para("    def toggle(self) -> None:", { run: { font: "Courier New", size: 20 } }));
children.push(para("        \"\"\"切换播放/暂停状态\"\"\"", { run: { font: "Courier New", size: 20 } }));
children.push(para("        ...", { run: { font: "Courier New", size: 20 } }));

children.push(para(""));
children.push(para("【6】Button类定义（ui.py）", { run: { bold: true } }));
children.push(para(""));
children.push(para("class Button:", { run: { font: "Courier New", size: 20 } }));
children.push(para("    \"\"\"按钮控件类：可点击的按钮组件\"\"\"", { run: { font: "Courier New", size: 20 } }));
children.push(para("", { run: { font: "Courier New", size: 20 } }));
children.push(para("    def __init__(self, rect: tuple, text: str, color: tuple = BTN_BG, text_color: tuple = WHITE) -> None:", { run: { font: "Courier New", size: 20 } }));
children.push(para("        self.rect: pygame.Rect = pygame.Rect(rect)", { run: { font: "Courier New", size: 20 } }));
children.push(para("        self.text: str = text", { run: { font: "Courier New", size: 20 } }));
children.push(para("        self.color: tuple = color", { run: { font: "Courier New", size: 20 } }));
children.push(para("        self.text_color: tuple = text_color", { run: { font: "Courier New", size: 20 } }));
children.push(para("        self.hovered: bool = False", { run: { font: "Courier New", size: 20 } }));
children.push(para("", { run: { font: "Courier New", size: 20 } }));
children.push(para("    def update(self, mx: int, my: int) -> None:", { run: { font: "Courier New", size: 20 } }));
children.push(para("        \"\"\"更新按钮悬停状态\"\"\"", { run: { font: "Courier New", size: 20 } }));
children.push(para("        ...", { run: { font: "Courier New", size: 20 } }));
children.push(para("", { run: { font: "Courier New", size: 20 } }));
children.push(para("    def draw(self, screen: pygame.Surface, font: pygame.font.Font) -> None:", { run: { font: "Courier New", size: 20 } }));
children.push(para("        \"\"\"绘制按钮\"\"\"", { run: { font: "Courier New", size: 20 } }));
children.push(para("        ...", { run: { font: "Courier New", size: 20 } }));
children.push(para("", { run: { font: "Courier New", size: 20 } }));
children.push(para("    def clicked(self) -> bool:", { run: { font: "Courier New", size: 20 } }));
children.push(para("        \"\"\"判断按钮是否被点击\"\"\"", { run: { font: "Courier New", size: 20 } }));
children.push(para("        ...", { run: { font: "Courier New", size: 20 } }));

children.push(para(""));
children.push(para("【7】ConfigPanel类定义（ui.py）", { run: { bold: true } }));
children.push(para(""));
children.push(para("class ConfigPanel:", { run: { font: "Courier New", size: 20 } }));
children.push(para("    \"\"\"配置面板类：参数配置界面容器\"\"\"", { run: { font: "Courier New", size: 20 } }));
children.push(para("", { run: { font: "Courier New", size: 20 } }));
children.push(para("    def __init__(self, screen_w: int, screen_h: int) -> None:", { run: { font: "Courier New", size: 20 } }));
children.push(para("        self.visible: bool = False", { run: { font: "Courier New", size: 20 } }));
children.push(para("        self.screen_w: int = screen_w", { run: { font: "Courier New", size: 20 } }));
children.push(para("        self.screen_h: int = screen_h", { run: { font: "Courier New", size: 20 } }));
children.push(para("        self.fish_count: int = 5", { run: { font: "Courier New", size: 20 } }));
children.push(para("        self.speed_mult: float = 1.0", { run: { font: "Courier New", size: 20 } }));
children.push(para("        self.cross_screen: bool = True", { run: { font: "Courier New", size: 20 } }));
children.push(para("        ...  # 初始化多个Button组件", { run: { font: "Courier New", size: 20 } }));
children.push(para("", { run: { font: "Courier New", size: 20 } }));
children.push(para("    def toggle(self) -> bool:", { run: { font: "Courier New", size: 20 } }));
children.push(para("        \"\"\"切换面板显示/隐藏\"\"\"", { run: { font: "Courier New", size: 20 } }));
children.push(para("        ...", { run: { font: "Courier New", size: 20 } }));
children.push(para("", { run: { font: "Courier New", size: 20 } }));
children.push(para("    def handle_click(self) -> tuple or None:", { run: { font: "Courier New", size: 20 } }));
children.push(para("        \"\"\"处理鼠标点击事件\"\"\"", { run: { font: "Courier New", size: 20 } }));
children.push(para("        ...", { run: { font: "Courier New", size: 20 } }));
children.push(para("", { run: { font: "Courier New", size: 20 } }));
children.push(para("    def draw(self, screen: pygame.Surface, fish_count: int, speed_mult: float, cross_screen: bool, host_count: int, my_id: int, fps: float) -> None:", { run: { font: "Courier New", size: 20 } }));
children.push(para("        \"\"\"绘制配置面板\"\"\"", { run: { font: "Courier New", size: 20 } }));
children.push(para("        ...", { run: { font: "Courier New", size: 20 } }));

// ── 三、系统界面设计 ──
children.push(heading(HeadingLevel.HEADING_1, "三、系统界面设计"));

children.push(para(""));
children.push(para("系统界面布局图：", { run: { bold: true } }));
children.push(para(""));
children.push(para("┌─────────────────────────────────────────────┐", { run: { font: "Courier New", size: 18 } }));
children.push(para("│           深蓝色渐变背景                     │", { run: { font: "Courier New", size: 18 } }));
children.push(para("│                                             │", { run: { font: "Courier New", size: 18 } }));
children.push(para("│     🐟    🐟                                 │", { run: { font: "Courier New", size: 18 } }));
children.push(para("│           🐟      🐟                         │", { run: { font: "Courier New", size: 18 } }));
children.push(para("│                         🐟                   │", { run: { font: "Courier New", size: 18 } }));
children.push(para("│     🐟                                        │", { run: { font: "Courier New", size: 18 } }));
children.push(para("│                 🐟         🐟                 │", { run: { font: "Courier New", size: 18 } }));
children.push(para("│                                             │", { run: { font: "Courier New", size: 18 } }));
children.push(para("│ ┌──────────────┐                             │", { run: { font: "Courier New", size: 18 } }));
children.push(para("│ │ FPS: 50      │                             │", { run: { font: "Courier New", size: 18 } }));
children.push(para("│ │ fish: 5      │                             │", { run: { font: "Courier New", size: 18 } }));
children.push(para("│ │ hosts: 3     │                             │", { run: { font: "Courier New", size: 18 } }));
children.push(para("│ │ me: host #2  │                             │", { run: { font: "Courier New", size: 18 } }));
children.push(para("│ └──────────────┘                             │", { run: { font: "Courier New", size: 18 } }));
children.push(para("└─────────────────────────────────────────────┘", { run: { font: "Courier New", size: 18 } }));

children.push(para(""));
children.push(para("界面设计说明：", { run: { bold: true } }));
children.push(bulletItem("主界面：深蓝色渐变背景，显示鱼群游动动画，左上角显示HUD信息面板（FPS、鱼数量、主机数量、自身ID）"));
children.push(bulletItem("HUD面板：半透明黑色背景，显示系统运行状态信息，固定在左上角，不遮挡主要动画区域"));
children.push(bulletItem("配置面板（Tab键切换）：中央弹出半透明面板，包含鱼数量滑块、速度滑块、跨屏联动开关、暂停/重置按钮"));
children.push(bulletItem("鱼精灵：彩色椭圆身体+三角形尾巴+眼睛，大小和颜色随机，支持动态游动和边界反弹"));

children.push(para(""));
children.push(para("界面交互设计：", { run: { bold: true } }));
children.push(bulletItem("Tab键：打开/关闭配置面板"));
children.push(bulletItem("鼠标点击：配置面板内的按钮交互（滑块调节、开关切换、暂停重置）"));
children.push(bulletItem("ESC键：退出程序"));

// ── 四、拟采用的项目开发平台 ──
children.push(heading(HeadingLevel.HEADING_1, "四、拟采用的项目开发平台"));

children.push(para(""));
children.push(para("开发平台与工具：", { run: { bold: true } }));
children.push(bulletItem("编程语言：Python 3.7+"));
children.push(bulletItem("图形库：Pygame 2.x（跨平台2D游戏开发库）"));
children.push(bulletItem("网络库：Python内置socket库（UDP网络通信）"));
children.push(bulletItem("配置文件：INI格式（使用configparser标准库）"));
children.push(bulletItem("代码编辑器：Visual Studio Code / PyCharm"));
children.push(bulletItem("版本控制：Git"));
children.push(bulletItem("文档生成：docx库（自动生成Word文档）"));

children.push(para(""));
children.push(para("运行环境：", { run: { bold: true } }));
children.push(bulletItem("操作系统：Windows 10/11、macOS、Linux"));
children.push(bulletItem("Python版本：3.7及以上"));
children.push(bulletItem("依赖库：pygame、configparser（标准库）、socket（标准库）"));
children.push(bulletItem("网络环境：支持UDP广播的局域网（关闭防火墙或开放6000-6009端口）"));

children.push(para(""));
children.push(para("开发语言特点：", { run: { bold: true } }));
children.push(bulletItem("Python：语法简洁、开发效率高、丰富的第三方库支持、跨平台兼容性好"));
children.push(bulletItem("Pygame：专注于2D图形、轻量级、学习曲线平缓、适合游戏开发教学"));
children.push(bulletItem("socket：Python标准库、无需额外安装、支持TCP/UDP协议、适合网络编程实践"));

// ── 五、项目分工 ──
children.push(heading(HeadingLevel.HEADING_1, "五、项目分工"));

children.push(para(""));
children.push(para("本项目为个人项目，所有功能模块由单人完成。具体分工如下：", { run: { bold: true } }));
children.push(emptyLine());

children.push(para("【1】系统架构设计", { run: { bold: true } }));
children.push(indentItem("负责人：项目开发者"));
children.push(indentItem("职责：设计P2P分布式架构、确定模块划分、定义模块接口、制定通信协议"));

children.push(para(""));
children.push(para("【2】核心功能开发", { run: { bold: true } }));
children.push(indentItem("负责人：项目开发者"));
children.push(indentItem("职责：实现鱼群动画渲染（fish_entity.py、renderer.py）、实现网络通信（network.py、message.py）"));

children.push(para(""));
children.push(para("【3】辅助功能开发", { run: { bold: true } }));
children.push(indentItem("负责人：项目开发者"));
children.push(indentItem("职责：实现音效管理（audio_manager.py）、配置系统（config.py）、UI界面（ui.py）"));

children.push(para(""));
children.push(para("【4】系统集成与测试", { run: { bold: true } }));
children.push(indentItem("负责人：项目开发者"));
children.push(indentItem("职责：集成各模块、调试跨平台兼容性、性能测试、多主机联机测试"));

children.push(para(""));
children.push(para("【5】文档编写", { run: { bold: true } }));
children.push(indentItem("负责人：项目开发者"));
children.push(indentItem("职责：编写需求分析文档、初步设计文档、用户手册、开发日志、技术文档"));

// ── 创建文档 ──
const doc = new Document({
  creator: "局域网多屏联动游鱼动画系统",
  title: "初步设计文档",
  description: "集中实践环节阶段检查",
  sections: [{
    properties: {
      page: {
        margin: {
          top: 1440,
          right: 1440,
          bottom: 1440,
          left: 1440,
        },
      },
    },
    children: children,
  }],
});

// ── write ──
const outPath = "局域网多屏联动游鱼动画系统—初步设计.docx";
Packer.toBuffer(doc).then(buf => {
  fs.writeFileSync(outPath, buf);
  console.log("✅ Written:", outPath);
  console.log("   Size:", (buf.length / 1024).toFixed(1), "KB");
});
