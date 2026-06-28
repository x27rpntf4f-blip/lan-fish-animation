const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  AlignmentType, LevelFormat, HeadingLevel, BorderStyle, WidthType,
  ShadingType, PageBreak, PageNumber, Header, Footer
} = require("docx");

// ── helpers ──
const border = { style: BorderStyle.SINGLE, size: 1, color: "999999" };
const borders = { top: border, bottom: border, left: border, right: border };
const cellMargins = { top: 60, bottom: 60, left: 100, right: 100 };

function heading(level, text) {
  return new Paragraph({ heading: level, children: [new TextRun({ text, font: "Arial", bold: true })] });
}

function para(text, opts = {}) {
  return new Paragraph({
    spacing: { after: 120, line: 360 },
    ...opts,
    children: [new TextRun({ text, font: "Arial", size: 24, ...opts.run })]
  });
}

function multiRunPara(runs, opts = {}) {
  return new Paragraph({
    spacing: { after: 120, line: 360 },
    ...opts,
    children: runs.map(r => new TextRun({ font: "Arial", size: 24, ...r }))
  });
}

function bulletItem(text, ref = "bullets", level = 0) {
  return new Paragraph({
    numbering: { reference: ref, level },
    spacing: { after: 80, line: 340 },
    children: [new TextRun({ text, font: "Arial", size: 24 })]
  });
}

function numberedItem(text, ref = "numbers", level = 0) {
  return new Paragraph({
    numbering: { reference: ref, level },
    spacing: { after: 80, line: 340 },
    children: [new TextRun({ text, font: "Arial", size: 24 })]
  });
}

function cell(text, opts = {}) {
  const children = [];
  if (typeof text === "string") {
    children.push(new Paragraph({
      spacing: { after: 60, line: 300 },
      children: [new TextRun({ text, font: "Arial", size: 20, bold: opts.bold || false })]
    }));
  } else if (Array.isArray(text)) {
    text.forEach(t => {
      children.push(new Paragraph({
        spacing: { after: 40, line: 280 },
        children: [new TextRun({ text: t, font: "Arial", size: 20 })]
      }));
    });
  }
  return new TableCell({
    borders,
    margins: cellMargins,
    width: { size: opts.width || 2000, type: WidthType.DXA },
    shading: opts.shading ? { fill: opts.shading, type: ShadingType.CLEAR } : undefined,
    verticalAlign: "center",
    children
  });
}

function headerCell(text, width) {
  return cell(text, { width, bold: true, shading: "D5E8F0" });
}

// ── content ──
const children = [];

// Title page
children.push(new Paragraph({ spacing: { before: 3600 }, children: [] }));
children.push(new Paragraph({
  alignment: AlignmentType.CENTER,
  spacing: { after: 200 },
  children: [new TextRun({ text: "局域网多屏联动游鱼动画系统", font: "Arial", size: 44, bold: true })]
}));
children.push(new Paragraph({
  alignment: AlignmentType.CENTER,
  spacing: { after: 600 },
  children: [new TextRun({ text: "需求分析说明书", font: "Arial", size: 36 })]
}));
children.push(new Paragraph({
  alignment: AlignmentType.CENTER,
  spacing: { after: 200 },
  children: [new TextRun({ text: "技术栈：Python + Pygame  |  通信：UDP 广播/单播  |  动画：2D", font: "Arial", size: 22, color: "666666" })]
}));
children.push(new Paragraph({
  alignment: AlignmentType.CENTER,
  spacing: { after: 200 },
  children: [new TextRun({ text: "版本：v1.0  |  2026-05", font: "Arial", size: 22, color: "666666" })]
}));
children.push(new Paragraph({ children: [new PageBreak()] }));

// ══════════ 2 需求分析 ══════════
children.push(heading(HeadingLevel.HEADING_1, "2  需求分析"));

// ── 2.1 系统需求概述 ──
children.push(heading(HeadingLevel.HEADING_2, "2.1  系统需求概述"));

children.push(para("在同一个局域网内的多台主机运行本系统，多条游鱼在各主机屏幕之间自由游动。当鱼游出某屏幕边界时，自动进入相邻主机的屏幕，实现跨屏联动效果。配合水流音效，打造沉浸式网络游鱼展示系统。"));

children.push(para(""));
children.push(para("系统目标：", { run: { bold: true } }));

const goals = [
  "自动发现局域网内运行本系统的主机，建立多屏联动组网",
  "支持至少 3 台主机组成多屏阵列",
  "每条鱼独立运动：随机方向、速度、大小、颜色，具备自然摆动动画",
  "鱼游出屏幕边界时无缝跨屏切换，延迟 < 100ms",
  "全程水流背景音效，支持独立启停控制",
  "提供图形化参数配置面板：鱼数量、游动速度倍率、联动开关",
  "支持窗口模式与全屏模式一键切换",
  "动画帧率 ≥ 25 FPS，连续运行 30 分钟不崩溃"
];
goals.forEach(g => children.push(bulletItem(g)));

// ── 2.1.1 技术架构概述 ──
children.push(heading(HeadingLevel.HEADING_2, "2.1.1  技术架构概述"));

children.push(para(""));
children.push(para("一、系统整体架构", { run: { bold: true, size: 26 } }));

children.push(para("本系统采用 P2P（Peer-to-Peer）无中心化分布式架构，各主机地位对等，通过 UDP 广播实现自动发现与组网，无需中心服务器协调。各主机独立运行，通过网络通信实现鱼的位置同步与跨屏联动。"));

children.push(para(""));
children.push(para("系统整体架构图（Mermaid）：", { run: { bold: true } }));
children.push(para(""));
children.push(para("graph TB", { run: { font: "Courier New", size: 18 } }));
children.push(para("  subgraph 局域网_LAN", { run: { font: "Courier New", size: 18 } }));
children.push(para("    subgraph 主机A_Host_A", { run: { font: "Courier New", size: 18 } }));
children.push(para("      A1[UDP Socket 6000]", { run: { font: "Courier New", size: 18 } }));
children.push(para("      A2[鱼群动画渲染]", { run: { font: "Courier New", size: 18 } }));
children.push(para("      A3[音效播放]", { run: { font: "Courier New", size: 18 } }));
children.push(para("      A1 --> A2", { run: { font: "Courier New", size: 18 } }));
children.push(para("      A1 -.-> A3", { run: { font: "Courier New", size: 18 } }));
children.push(para("    end", { run: { font: "Courier New", size: 18 } }));
children.push(para("    subgraph 主机B_Host_B", { run: { font: "Courier New", size: 18 } }));
children.push(para("      B1[UDP Socket 6001]", { run: { font: "Courier New", size: 18 } }));
children.push(para("      B2[鱼群动画渲染]", { run: { font: "Courier New", size: 18 } }));
children.push(para("      B3[音效播放]", { run: { font: "Courier New", size: 18 } }));
children.push(para("      B1 --> B2", { run: { font: "Courier New", size: 18 } }));
children.push(para("      B1 -.-> B3", { run: { font: "Courier New", size: 18 } }));
children.push(para("    end", { run: { font: "Courier New", size: 18 } }));
children.push(para("    subgraph 主机C_Host_C", { run: { font: "Courier New", size: 18 } }));
children.push(para("      C1[UDP Socket 6002]", { run: { font: "Courier New", size: 18 } }));
children.push(para("      C2[鱼群动画渲染]", { run: { font: "Courier New", size: 18 } }));
children.push(para("      C3[音效播放]", { run: { font: "Courier New", size: 18 } }));
children.push(para("      C1 --> C2", { run: { font: "Courier New", size: 18 } }));
children.push(para("      C1 -.-> C3", { run: { font: "Courier New", size: 18 } }));
children.push(para("    end", { run: { font: "Courier New", size: 18 } }));
children.push(para("    A1 <-->|UDP 广播 HELLO/ACK| B1", { run: { font: "Courier New", size: 18 } }));
children.push(para("    B1 <-->|UDP 广播 HELLO/ACK| C1", { run: { font: "Courier New", size: 18 } }));
children.push(para("    A1 -.->|UDP 单播 TRANSFER| B1", { run: { font: "Courier New", size: 18 } }));
children.push(para("    B1 -.->|UDP 单播 TRANSFER| C1", { run: { font: "Courier New", size: 18 } }));
children.push(para("  end", { run: { font: "Courier New", size: 18 } }));

children.push(para(""));
children.push(para("架构特点：", { run: { bold: true } }));
children.push(bulletItem("无中心化：各主机地位对等，通过 UDP 广播自动发现，无需中心服务器"));
children.push(bulletItem("自动组网：启动时各主机广播 HELLO 消息，按 IP 排序确定屏幕从左到右的拓扑关系"));
children.push(bulletItem("实时同步：通过 UDP 单播实时传输鱼的位置、方向、速度等状态，实现跨屏联动"));
children.push(bulletItem("容错机制：心跳机制检测主机离线，超时自动从拓扑中移除，保证系统稳定性"));

children.push(para(""));
children.push(para("二、线程模型", { run: { bold: true, size: 26 } }));

children.push(para("系统采用主线程 + 后台网络线程的双线程架构。Pygame 在 macOS 上严格要求在主线程运行渲染和事件处理，因此网络接收操作必须放在独立线程中。"));

children.push(para(""));
children.push(para("线程模型架构图（Mermaid）：", { run: { bold: true } }));
children.push(para(""));
children.push(para("graph LR", { run: { font: "Courier New", size: 20 } }));
children.push(para("  subgraph 主线程_Pygame", { run: { font: "Courier New", size: 20 } }));
children.push(para("    A[事件处理] --> B[更新鱼位置]", { run: { font: "Courier New", size: 20 } }));
children.push(para("    B --> C[边界检测]", { run: { font: "Courier New", size: 20 } }));
children.push(para("    C -->|越界| D[UDP sendto 非阻塞发送]", { run: { font: "Courier New", size: 20 } }));
children.push(para("    C -->|未越界| E[渲染鱼群]", { run: { font: "Courier New", size: 20 } }));
children.push(para("    D --> E", { run: { font: "Courier New", size: 20 } }));
children.push(para("    E --> F[渲染 HUD]", { run: { font: "Courier New", size: 20 } }));
children.push(para("    F --> G[pygame.display.flip]", { run: { font: "Courier New", size: 20 } }));
children.push(para("    G -->|非阻塞取消息| H[处理 queue 中收到的消息]", { run: { font: "Courier New", size: 20 } }));
children.push(para("    H --> A", { run: { font: "Courier New", size: 20 } }));
children.push(para("  end", { run: { font: "Courier New", size: 20 } }));
children.push(para("  subgraph 网络线程_后台daemon", { run: { font: "Courier New", size: 20 } }));
children.push(para("    I[socket.recvfrom 阻塞] --> J[queue.put 放入队列]", { run: { font: "Courier New", size: 20 } }));
children.push(para("    J --> I", { run: { font: "Courier New", size: 20 } }));
children.push(para("  end", { run: { font: "Courier New", size: 20 } }));
children.push(para("  E -.->|queue.Queue 线程安全| H", { run: { font: "Courier New", size: 20 } }));

children.push(para(""));
children.push(para("线程设计要点：", { run: { bold: true } }));
children.push(bulletItem("主线程：Pygame 窗口初始化、事件处理、鱼位置更新、边界检测、UDP 发送（sendto 非阻塞）、鱼群渲染、HUD 渲染、帧率控制（clock.tick）"));
children.push(bulletItem("网络线程（daemon）：while 循环执行 socket.recvfrom(512) 阻塞接收消息，收到后放入 queue.Queue（Python 标准库线程安全队列）"));
children.push(bulletItem("线程通信：主线程每帧通过 queue.get_nowait() 非阻塞方式取出所有待处理消息并处理，不阻塞帧循环"));
children.push(bulletItem("线程退出：主线程退出时设置 running = False，网络线程的 recvfrom 因设置了 0.5s 超时而自然退出，daemon 属性确保程序退出时线程不阻塞"));

children.push(para(""));
children.push(para("三、模块依赖关系", { run: { bold: true, size: 26 } }));

children.push(para(""));
children.push(para("模块依赖关系图（Mermaid）：", { run: { bold: true } }));
children.push(para(""));
children.push(para("graph TB", { run: { font: "Courier New", size: 18 } }));
children.push(para("  subgraph 核心模块", { run: { font: "Courier New", size: 18 } }));
children.push(para("    MAIN[main.py<br/>主循环入口]", { run: { font: "Courier New", size: 18 } }));
children.push(para("    FISH[fish_entity.py<br/>鱼实体类]", { run: { font: "Courier New", size: 18 } }));
children.push(para("    RENDER[renderer.py<br/>渲染器]", { run: { font: "Courier New", size: 18 } }));
children.push(para("    NETWORK[network.py<br/>网络管理]", { run: { font: "Courier New", size: 18 } }));
children.push(para("    MSG[message.py<br/>消息序列化]", { run: { font: "Courier New", size: 18 } }));
children.push(para("    AUDIO[audio_manager.py<br/>音效管理]", { run: { font: "Courier New", size: 18 } }));
children.push(para("    CONFIG[config.py<br/>配置管理]", { run: { font: "Courier New", size: 18 } }));
children.push(para("    UI[ui.py<br/>UI 配置面板]", { run: { font: "Courier New", size: 18 } }));
children.push(para("  end", { run: { font: "Courier New", size: 18 } }));
children.push(para("  subgraph 外部依赖", { run: { font: "Courier New", size: 18 } }));
children.push(para("    PYGAME[Pygame<br/>图形渲染]", { run: { font: "Courier New", size: 18 } }));
children.push(para("    SOCKET[Socket<br/>网络通信]", { run: { font: "Courier New", size: 18 } }));
children.push(para("  end", { run: { font: "Courier New", size: 18 } }));
children.push(para("  MAIN --> FISH", { run: { font: "Courier New", size: 18 } }));
children.push(para("  MAIN --> RENDER", { run: { font: "Courier New", size: 18 } }));
children.push(para("  MAIN --> NETWORK", { run: { font: "Courier New", size: 18 } }));
children.push(para("  MAIN --> AUDIO", { run: { font: "Courier New", size: 18 } }));
children.push(para("  MAIN --> CONFIG", { run: { font: "Courier New", size: 18 } }));
children.push(para("  MAIN --> UI", { run: { font: "Courier New", size: 18 } }));
children.push(para("  NETWORK --> MSG", { run: { font: "Courier New", size: 18 } }));
children.push(para("  NETWORK --> SOCKET", { run: { font: "Courier New", size: 18 } }));
children.push(para("  RENDER --> FISH", { run: { font: "Courier New", size: 18 } }));
children.push(para("  RENDER --> PYGAME", { run: { font: "Courier New", size: 18 } }));
children.push(para("  AUDIO --> PYGAME", { run: { font: "Courier New", size: 18 } }));

children.push(para(""));
children.push(para("模块职责说明：", { run: { bold: true } }));
children.push(bulletItem("main.py：系统入口，负责初始化 Pygame、创建 UDP Socket、启动网络线程、管理主循环，协调各模块工作"));
children.push(bulletItem("fish_entity.py：定义 Fish 类，管理单条鱼的属性（ID、位置、方向、速度、大小、颜色）和行为（update 位置更新、bounce 边界反弹）"));
children.push(bulletItem("renderer.py：封装 Pygame 渲染函数，负责绘制深蓝色渐变背景、动态鱼精灵（椭圆+三角形+旋转）、水波纹特效、HUD 信息面板"));
children.push(bulletItem("network.py：实现 NetworkManager（Socket 管理、UDP 广播/单播、监听线程）和 HostRegistry（主机列表、心跳检测、拓扑管理）"));
children.push(bulletItem("message.py：定义六种消息类型的序列化/反序列化函数（HELLO/ACK/HEARTBEAT/TOPOLOGY/TRANSFER/GOODBYE），使用 struct 二进制编码"));
children.push(bulletItem("audio_manager.py：封装 pygame.mixer，提供水流背景音的加载、循环播放、暂停、音量控制功能"));
children.push(bulletItem("config.py：使用 configparser 读取/写入 config.ini，管理窗口尺寸、鱼数量、端口、心跳参数、音量等配置项"));
children.push(bulletItem("ui.py：实现 ConfigPanel 类，绘制参数配置面板（鱼数量滑块、速度滑块、跨屏开关、暂停/重置按钮），支持鼠标点击交互"));

children.push(para(""));
children.push(para("项目模块结构", { run: { bold: true, size: 26 } }));

const archTable = new Table({
  width: { size: 9026, type: WidthType.DXA },
  columnWidths: [2200, 2400, 4426],
  rows: [
    new TableRow({ children: [headerCell("模块文件", 2200), headerCell("职责", 2400), headerCell("依赖/说明", 4426)] }),
    new TableRow({ children: [cell("src/main.py", { width: 2200 }), cell("入口 + 主循环", { width: 2400 }), cell("调度所有模块，管理主循环（事件→更新→渲染），约 150 行", { width: 4426 })] }),
    new TableRow({ children: [cell("src/fish_entity.py", { width: 2200 }), cell("鱼实体类 Fish", { width: 2400 }), cell("鱼属性（ID/位置/方向/速度/大小/颜色）、update() 位置更新、边界反弹逻辑，约 120 行", { width: 4426 })] }),
    new TableRow({ children: [cell("src/renderer.py", { width: 2200 }), cell("渲染器", { width: 2400 }), cell("绘制鱼精灵（椭圆+三角形+旋转）、背景、水波纹特效、HUD 信息面板，依赖 fish_entity.py，约 200 行", { width: 4426 })] }),
    new TableRow({ children: [cell("src/network.py", { width: 2200 }), cell("UDP 通信 + 主机管理", { width: 2400 }), cell("NetworkManager（Socket 创建/广播/单播/监听线程）、HostRegistry（主机列表/心跳/拓扑），约 250 行", { width: 4426 })] }),
    new TableRow({ children: [cell("src/message.py", { width: 2200 }), cell("消息序列化/反序列化", { width: 2400 }), cell("pack/unpack 六种消息类型（HELLO/ACK/HEARTBEAT/TOPOLOGY/TRANSFER/GOODBYE），二进制编码，约 100 行", { width: 4426 })] }),
    new TableRow({ children: [cell("src/audio_manager.py", { width: 2200 }), cell("音效管理", { width: 2400 }), cell("水流背景音加载/循环播放/暂停/音量控制，pygame.mixer 封装，约 60 行", { width: 4426 })] }),
    new TableRow({ children: [cell("src/config.py", { width: 2200 }), cell("配置管理", { width: 2400 }), cell("读取/写入 config.ini，配置项包括窗口尺寸、鱼数量、端口、心跳参数、音量，约 50 行", { width: 4426 })] }),
  ]
});
children.push(archTable);

children.push(para(""));
children.push(para("关键技术决策", { run: { bold: true, size: 26 } }));

children.push(bulletItem("动画方案：2D 渲染，使用 Pygame 基本图元（椭圆+三角形+圆形）绘制鱼精灵，通过 pygame.transform.rotate 实现方向旋转，不依赖任何外部图片素材。原因：代码可控、无素材版权问题、答辩时能展示对图形学原理的理解"));
children.push(bulletItem("通信协议：采用 struct.pack/unpack 二进制序列化，而非 JSON。原因：单条鱼传输数据仅 28 字节（JSON 约 150 字节），序列化开销接近零，在 60FPS 下频繁跨屏传输时不产生可感知的 CPU 开销"));
children.push(bulletItem("传输层选择 UDP 而非 TCP。原因：① 跨屏鱼传输是实时流数据，允许少量丢包（鱼偶尔消失不影响体验）；② UDP 无连接建立延迟和拥塞控制开销，延迟更低；③ 通过应用层 Fish ID 去重和心跳机制弥补 UDP 的不可靠性"));
children.push(bulletItem("鱼全局 ID 编码：fish_id = (host_id << 8) | local_counter。高 8 位为主机编号，低 8 位为主机内自增序号。保证全局唯一且无需中心化分配"));

// ── 2.2 业务流程分析 ──
children.push(new Paragraph({ children: [new PageBreak()] }));
children.push(heading(HeadingLevel.HEADING_2, "2.2  业务流程分析"));

// 2.2.1
children.push(heading(HeadingLevel.HEADING_3, "2.2.1  总体业务流程分析"));

children.push(para("系统总体业务流程覆盖从启动到退出的完整生命周期，如下图所示（Mermaid 流程图），各阶段详述见后。"));

children.push(para(""));
children.push(para("总体流程（Mermaid）：", { run: { bold: true } }));
children.push(para(""));
children.push(para("flowchart TD", { run: { font: "Courier New", size: 20 } }));
children.push(para("  A[系统启动] --> B[加载配置文件]", { run: { font: "Courier New", size: 20 } }));
children.push(para("  B --> C[初始化 Pygame 窗口与音效]", { run: { font: "Courier New", size: 20 } }));
children.push(para("  C --> D[创建 UDP Socket 绑定端口]", { run: { font: "Courier New", size: 20 } }));
children.push(para("  D --> E[广播自身节点信息]", { run: { font: "Courier New", size: 20 } }));
children.push(para("  E --> F[启动监听线程接收其他主机]", { run: { font: "Courier New", size: 20 } }));
children.push(para("  F --> G[收集主机列表, 确定屏幕拓扑]", { run: { font: "Courier New", size: 20 } }));
children.push(para("  G --> H[随机生成初始鱼群]", { run: { font: "Courier New", size: 20 } }));
children.push(para("  H --> I[进入主循环]", { run: { font: "Courier New", size: 20 } }));
children.push(para("  I --> J[事件处理(键盘/鼠标)]", { run: { font: "Courier New", size: 20 } }));
children.push(para("  J --> K[更新鱼群位置]", { run: { font: "Courier New", size: 20 } }));
children.push(para("  K --> L{检测边界越界?}", { run: { font: "Courier New", size: 20 } }));
children.push(para("  L -->|是| M[封装 TRANSFER 消息]", { run: { font: "Courier New", size: 20 } }));
children.push(para("  M --> N[UDP 单播至相邻主机]", { run: { font: "Courier New", size: 20 } }));
children.push(para("  N --> O[本机删除该鱼]", { run: { font: "Courier New", size: 20 } }));
children.push(para("  L -->|否| P[继续渲染]", { run: { font: "Courier New", size: 20 } }));
children.push(para("  O --> P", { run: { font: "Courier New", size: 20 } }));
children.push(para("  P --> Q[接收其他主机传来的鱼]", { run: { font: "Courier New", size: 20 } }));
children.push(para("  Q --> R[渲染所有鱼 + HUD + 水波纹]", { run: { font: "Courier New", size: 20 } }));
children.push(para("  R --> S[刷新显示 + 播放音效]", { run: { font: "Courier New", size: 20 } }));
children.push(para("  S --> T{退出?}", { run: { font: "Courier New", size: 20 } }));
children.push(para("  T -->|否| I", { run: { font: "Courier New", size: 20 } }));
children.push(para("  T -->|是| U[广播 GOODBYE, 释放资源, 退出]", { run: { font: "Courier New", size: 20 } }));

children.push(para(""));
children.push(para("分步描述：", { run: { bold: true } }));

const overallSteps = [
  "系统启动与初始化：加载 config.ini 配置文件 → 初始化 Pygame 图形窗口（默认 800×600 窗口模式）→ 初始化音效模块（pygame.mixer）→ 创建 UDP Socket 并绑定端口",
  "局域网自动组网：广播自身节点信息（主机名、IP、端口）→ 监听其他节点广播 → 建立主机列表 → 按 IP 地址排序确定屏幕从左到右的拓扑关系",
  "游鱼生成：按配置数量（默认 5 条）随机创建鱼实体，每条鱼具备随机初始位置、游动方向、速度、体型大小及颜色",
  "主循环运行：事件处理（键盘快捷键、窗口事件）→ 鱼群位置更新（基于速度和方向）→ 边界碰撞检测 → 跨屏消息收发（UDP 异步处理）→ 鱼群渲染 → 音效播放",
  "跨屏联动：鱼游出屏幕边界 → 序列化鱼状态数据为二进制消息 → UDP 单播发送给对应方向的相邻主机 → 相邻主机接收消息 → 反序列化 → 在对侧边界生成鱼实体并继续游动",
  "系统退出：广播 GOODBYE 消息通知其他主机 → 关闭 UDP Socket → 释放音效资源 → 退出 Pygame → 程序结束"
];
overallSteps.forEach((s, i) => children.push(numberedItem(s, "overallSteps")));

// 2.2.2 网络组网
children.push(new Paragraph({ children: [new PageBreak()] }));
children.push(heading(HeadingLevel.HEADING_3, "2.2.2  网络组网子系统业务流程分析"));

children.push(para("网络组网子系统负责局域网内各主机节点的自动发现、拓扑协商与心跳维持。"));

children.push(para(""));
children.push(para("组网流程（Mermaid）：", { run: { bold: true } }));
children.push(para(""));
children.push(para("flowchart TD", { run: { font: "Courier New", size: 20 } }));
children.push(para("  A[启动 UDP Socket] --> B[广播 HELLO 消息]", { run: { font: "Courier New", size: 20 } }));
children.push(para("  B --> C[启动监听线程]", { run: { font: "Courier New", size: 20 } }));
children.push(para("  C --> D{收到 HELLO?}", { run: { font: "Courier New", size: 20 } }));
children.push(para("  D -->|是| E[回复 ACK 消息]", { run: { font: "Courier New", size: 20 } }));
children.push(para("  E --> F[将对方加入主机列表]", { run: { font: "Courier New", size: 20 } }));
children.push(para("  D -->|否| G{收到 ACK?}", { run: { font: "Courier New", size: 20 } }));
children.push(para("  G -->|是| F", { run: { font: "Courier New", size: 20 } }));
children.push(para("  G -->|否| H[继续监听]", { run: { font: "Courier New", size: 20 } }));
children.push(para("  F --> I[按 IP 排序确定拓扑]", { run: { font: "Courier New", size: 20 } }));
children.push(para("  I --> J[广播 TOPOLOGY 协商结果]", { run: { font: "Courier New", size: 20 } }));
children.push(para("  J --> K[确定左右相邻主机]", { run: { font: "Courier New", size: 20 } }));
children.push(para("  K --> L[组网完成, 每3秒发 HEARTBEAT]", { run: { font: "Courier New", size: 20 } }));
children.push(para("  L --> M{心跳超时 10s?}", { run: { font: "Courier New", size: 20 } }));
children.push(para("  M -->|是| N[移除离线主机, 重算拓扑]", { run: { font: "Courier New", size: 20 } }));
children.push(para("  M -->|否| L", { run: { font: "Courier New", size: 20 } }));

children.push(para(""));
children.push(para("详细说明：", { run: { bold: true } }));
children.push(bulletItem("启动时通过 UDP 端口 6000 广播 HELLO 消息，包含主机名、IP 地址和端口号"));
children.push(bulletItem("同时启动监听线程，持续接收其他主机的 HELLO 广播和 ACK 回复"));
children.push(bulletItem("收到 HELLO 后回复 ACK（含自身信息），收到 ACK 后将对方加入主机列表"));
children.push(bulletItem("按 IP 地址升序排列各主机，确定屏幕从左到右的物理位置，据此每个主机确定左邻/右邻"));
children.push(bulletItem("每 3 秒广播一次 HEARTBEAT 心跳消息，超过 10 秒未收到某主机心跳则判定其离线"));
children.push(bulletItem("主机离线或新主机加入时自动触发拓扑重算，动态更新相邻关系"));

// 2.2.3 跨屏通信
children.push(heading(HeadingLevel.HEADING_3, "2.2.3  跨屏通信子系统业务流程分析"));

children.push(para("跨屏通信子系统是本项目的核心模块，负责鱼实体在主机间的传输和状态同步。"));

children.push(para(""));
children.push(para("跨屏通信流程（Mermaid）：", { run: { bold: true } }));
children.push(para(""));
children.push(para("flowchart TD", { run: { font: "Courier New", size: 20 } }));
children.push(para("  A[每帧更新鱼位置] --> B{检测边界越界?}", { run: { font: "Courier New", size: 20 } }));
children.push(para("  B -->|未越界| C[正常游动, 继续渲染]", { run: { font: "Courier New", size: 20 } }));
children.push(para("  B -->|越界| D[判断越界方向: 左/右/上/下]", { run: { font: "Courier New", size: 20 } }));
children.push(para("  D --> E{对应方向有相邻主机?}", { run: { font: "Courier New", size: 20 } }));
children.push(para("  E -->|无| F[边界反弹: 反转方向角]", { run: { font: "Courier New", size: 20 } }));
children.push(para("  F --> C", { run: { font: "Courier New", size: 20 } }));
children.push(para("  E -->|有| G[查找相邻主机 IP:Port]", { run: { font: "Courier New", size: 20 } }));
children.push(para("  G --> H[序列化鱼状态为二进制 TRANSFER 消息]", { run: { font: "Courier New", size: 20 } }));
children.push(para("  H --> I[UDP 单播发送至目标主机]", { run: { font: "Courier New", size: 20 } }));
children.push(para("  I --> J[本机从鱼列表中删除该鱼]", { run: { font: "Courier New", size: 20 } }));
children.push(para("  J --> K[目标主机监听线程收到消息]", { run: { font: "Courier New", size: 20 } }));
children.push(para("  K --> L[反序列化, 合法性校验]", { run: { font: "Courier New", size: 20 } }));
children.push(para("  L --> M{校验通过?}", { run: { font: "Courier New", size: 20 } }));
children.push(para("  M -->|否| N[丢弃消息]", { run: { font: "Courier New", size: 20 } }));
children.push(para("  M -->|是| O{Fish ID 已存在?}", { run: { font: "Courier New", size: 20 } }));
children.push(para("  O -->|是| N", { run: { font: "Courier New", size: 20 } }));
children.push(para("  O -->|否| P[在对侧边界创建鱼实体]", { run: { font: "Courier New", size: 20 } }));
children.push(para("  P --> C", { run: { font: "Courier New", size: 20 } }));

children.push(para(""));
children.push(para("关键设计要点：", { run: { bold: true } }));
children.push(bulletItem("每帧（约 16.7ms @ 60FPS）检测每条鱼的屏幕坐标是否超出 [0, width] × [0, height] 范围"));
children.push(bulletItem("超出方向判断：x < 0 为左越界、x > width 为右越界、y < 0 为上越界、y > height 为下越界"));
children.push(bulletItem("发送端在鱼刚接触边界时即触发传输（而非完全离开后），以保证接收端有足够时间准备"));
children.push(bulletItem("接收端在对应边界外 1-2 像素位置生成鱼，例如：从右侧进入则在 x = -2 处创建，下一帧自然进入屏幕"));
children.push(bulletItem("使用二进制序列化（struct.pack/unpack）而非 JSON，单条鱼传输数据仅约 21 字节，大幅降低延迟"));
children.push(bulletItem("按 Fish ID 去重，防止因 UDP 重传导致同一鱼在接收端出现多个副本"));

// 2.2.4 动画渲染
children.push(heading(HeadingLevel.HEADING_3, "2.2.4  动画渲染子系统业务流程分析"));

children.push(para(""));
children.push(para("渲染流程（Mermaid）：", { run: { bold: true } }));
children.push(para(""));
children.push(para("flowchart TD", { run: { font: "Courier New", size: 20 } }));
children.push(para("  A[帧开始] --> B[清屏: 填充背景色(深蓝渐变)]", { run: { font: "Courier New", size: 20 } }));
children.push(para("  B --> C[更新鱼位置: x += cos(dir)*speed*dt]", { run: { font: "Courier New", size: 20 } }));
children.push(para("  C --> D[更新鱼摆尾相位: phase += speed*dt]", { run: { font: "Courier New", size: 20 } }));
children.push(para("  D --> E[绘制水波纹: 半透明圆扩散衰减]", { run: { font: "Courier New", size: 20 } }));
children.push(para("  E --> F[逐条绘制鱼精灵]", { run: { font: "Courier New", size: 20 } }));
children.push(para("  F --> G[鱼身: 椭圆 + 尾鳍: 三角形]", { run: { font: "Courier New", size: 20 } }));
children.push(para("  G --> H[应用旋转: 按 direction 角旋转]", { run: { font: "Courier New", size: 20 } }));
children.push(para("  H --> I[绘制 HUD 信息(联机数/鱼数/FPS)]", { run: { font: "Courier New", size: 20 } }));
children.push(para("  I --> J[pygame.display.flip 刷新显示]", { run: { font: "Courier New", size: 20 } }));
children.push(para("  J --> K[clock.tick 控制帧率]", { run: { font: "Courier New", size: 20 } }));
children.push(para("  K --> A", { run: { font: "Courier New", size: 20 } }));

children.push(para(""));
children.push(para("详细说明：", { run: { bold: true } }));
children.push(bulletItem("鱼精灵使用 Pygame 基本图元绘制：椭圆（pygame.draw.ellipse）作为鱼身 + 三角形（pygame.draw.polygon）作为尾鳍，通过 pygame.Surface 合成后旋转"));
children.push(bulletItem("摆动动画：尾鳍以正弦波角度摆动，相位 = 时间 × 速度系数，尾部摆动幅度 ±15°，频率与游动速度正相关"));
children.push(bulletItem("方向渐变旋转：鱼精灵以 direction 角度整体旋转（pygame.transform.rotate），使鱼头朝向游动方向"));
children.push(bulletItem("颜色系统：使用 HSV 色彩空间（随机色相），转换为 RGB 后填充，保证鱼之间色彩差异明显"));
children.push(bulletItem("水波纹特效：每条鱼周期性（每 0.5 秒）在其当前位置产生一个半透明圆形波纹，半径从 0 扩散至 30 像素后消失，使用 alpha 渐变"));
children.push(bulletItem("HUD 信息：屏幕左上角叠加半透明信息面板，显示联机主机数量、当前鱼数量、实时 FPS"));

// 2.2.5 音效
children.push(heading(HeadingLevel.HEADING_3, "2.2.5  音效子系统业务流程分析"));

children.push(para("音效子系统负责背景水流声音的播放控制，流程相对简单："));
children.push(bulletItem("系统初始化时，使用 pygame.mixer.music.load() 加载水流背景音频文件（支持 WAV / OGG 格式）"));
children.push(bulletItem("调用 pygame.mixer.music.play(-1) 启动无限循环后台播放"));
children.push(bulletItem("用户按 M 键切换静音状态：调用 pygame.mixer.music.pause() / unpause()"));
children.push(bulletItem("音量可通过 config.ini 中的 volume 参数设置（0.0 - 1.0），通过 pygame.mixer.music.set_volume() 设置"));
children.push(bulletItem("程序退出时调用 pygame.mixer.music.stop() 停止播放，pygame.mixer.quit() 释放音频资源"));

// ── 2.3 系统功能需求概述 ──
children.push(new Paragraph({ children: [new PageBreak()] }));
children.push(heading(HeadingLevel.HEADING_2, "2.3  系统功能需求概述"));

// 2.3.1
children.push(heading(HeadingLevel.HEADING_3, "2.3.1  功能需求"));

children.push(para("功能需求按优先级分为三个层级：核心功能（P0，必须实现）、重要功能（P1，应当实现）、可选功能（P2，时间充裕时实现）。"));

children.push(para(""));
children.push(para("核心功能（P0）：", { run: { bold: true } }));

const p0 = [
  ["FR01", "局域网自动组网", "启动后自动发现同网段其他运行本系统的主机，建立多屏联动组网"],
  ["FR02", "屏幕拓扑管理", "自动确定各主机的左右/上下相邻关系，支持动态更新"],
  ["FR03", "2D 游鱼动画", "多条鱼独立游动，具备自然摆动、转向、变速动画效果"],
  ["FR04", "跨屏切换", "鱼游出屏幕边界后自动进入相邻主机对应位置，延迟 < 100ms"],
  ["FR05", "鱼群状态同步", "各主机间通过 UDP 实时同步鱼的位置、方向、速度等状态数据"]
];
p0.forEach(([id, name, desc]) => {
  children.push(bulletItem(`${id} ${name}：${desc}`));
});

children.push(para(""));
children.push(para("重要功能（P1）：", { run: { bold: true } }));
const p1 = [
  ["FR06", "参数配置面板", "可调整鱼数量（1-20条）、游动速度倍率（0.5x-2x），使用滑块控件"],
  ["FR07", "窗口/全屏切换", "一键（F11）切换窗口模式与全屏模式"],
  ["FR08", "水流音效", "循环播放背景水流声，支持独立开关（M 键）"],
  ["FR09", "联机状态显示", "屏幕 HUD 实时展示当前联机主机数量、鱼数量、运行状态"],
  ["FR10", "动态加入/退出", "支持主机随时加入或退出，拓扑自动调整，不影响整体运行"]
];
p1.forEach(([id, name, desc]) => {
  children.push(bulletItem(`${id} ${name}：${desc}`));
});

children.push(para(""));
children.push(para("可选功能（P2）：", { run: { bold: true } }));
const p2 = [
  ["FR11", "水波纹特效", "鱼游动时产生半透明水波纹扩散效果"],
  ["FR12", "演示暂停/重置", "支持暂停（P 键）和重置（R 键）所有鱼群状态"],
  ["FR13", "跨屏联动开关", "可关闭跨屏功能，仅在本机屏幕范围内游动"]
];
p2.forEach(([id, name, desc]) => {
  children.push(bulletItem(`${id} ${name}：${desc}`));
});

// 2.3.2 用例模型
children.push(heading(HeadingLevel.HEADING_3, "2.3.2  用例模型"));

children.push(para("本系统的参与者包括：用户（操作员）和系统自身（自动执行）。以下为用例图的 Mermaid 描述："));

children.push(para(""));
children.push(para("用例图（Mermaid）：", { run: { bold: true } }));
children.push(para(""));
children.push(para("graph TD", { run: { font: "Courier New", size: 20 } }));
children.push(para("  User((用户))", { run: { font: "Courier New", size: 20 } }));
children.push(para("  User --- UC01[UC01 启动系统]", { run: { font: "Courier New", size: 20 } }));
children.push(para("  User --- UC02[UC02 配置参数]", { run: { font: "Courier New", size: 20 } }));
children.push(para("  User --- UC03[UC03 切换全屏/窗口]", { run: { font: "Courier New", size: 20 } }));
children.push(para("  User --- UC04[UC04 开关音效]", { run: { font: "Courier New", size: 20 } }));
children.push(para("  User --- UC05[UC05 暂停/重置演示]", { run: { font: "Courier New", size: 20 } }));
children.push(para("  User --- UC06[UC06 开关跨屏联动]", { run: { font: "Courier New", size: 20 } }));
children.push(para("  User --- UC07[UC07 查看联机状态]", { run: { font: "Courier New", size: 20 } }));
children.push(para("  User --- UC08[UC08 退出系统]", { run: { font: "Courier New", size: 20 } }));
children.push(para("  System((系统))", { run: { font: "Courier New", size: 20 } }));
children.push(para("  System --- UC09[UC09 自动组网]", { run: { font: "Courier New", size: 20 } }));
children.push(para("  System --- UC10[UC10 鱼群游动与渲染]", { run: { font: "Courier New", size: 20 } }));
children.push(para("  System --- UC11[UC11 跨屏切换与状态同步]", { run: { font: "Courier New", size: 20 } }));
children.push(para("  System --- UC12[UC12 动态加入/退出处理]", { run: { font: "Courier New", size: 20 } }));
children.push(para("  System --- UC13[UC13 心跳维持与超时检测]", { run: { font: "Courier New", size: 20 } }));

children.push(para(""));
children.push(para("用例分类说明：", { run: { bold: true } }));
children.push(bulletItem("用户触发的用例（UC01-UC08）：由用户通过界面操作或键盘快捷键主动发起"));
children.push(bulletItem("系统自动执行的用例（UC09-UC13）：由系统在后台自动完成，无需用户干预"));

// 2.3.3 用例描述
children.push(new Paragraph({ children: [new PageBreak()] }));
children.push(heading(HeadingLevel.HEADING_3, "2.3.3  用例描述"));

children.push(para("以下对 6 个核心用例进行详细描述，每项包含：用例编号、用例名称、参与者、前置条件、后置条件、基本事件流、异常事件流。"));

// UC01
children.push(para(""));
children.push(para("用例 UC01：启动系统", { run: { bold: true, size: 26 } }));
children.push(para(""));

const uc01Table = new Table({
  width: { size: 9026, type: WidthType.DXA },
  columnWidths: [2200, 6826],
  rows: [
    new TableRow({ children: [headerCell("项目", 2200), headerCell("说明", 6826)] }),
    new TableRow({ children: [cell("用例编号", { width: 2200 }), cell("UC01", { width: 6826 })] }),
    new TableRow({ children: [cell("用例名称", { width: 2200 }), cell("启动系统", { width: 6826 })] }),
    new TableRow({ children: [cell("参与者", { width: 2200 }), cell("用户（操作员）", { width: 6826 })] }),
    new TableRow({ children: [cell("前置条件", { width: 2200 }), cell("主机已安装 Python 3.9+ 及依赖库（pygame, socket, struct, configparser, threading）", { width: 6826 })] }),
    new TableRow({ children: [cell("后置条件", { width: 2200 }), cell("系统进入主循环，窗口正常显示，鱼群开始游动", { width: 6826 })] }),
    new TableRow({ children: [cell("基本事件流", { width: 2200 }), cell([
      "1. 用户双击启动程序",
      "2. 系统加载配置文件（config.ini），读取窗口尺寸、鱼数量、端口等参数",
      "3. 初始化 Pygame 图形窗口（默认 800×600，窗口模式）",
      "4. 初始化音效模块，加载水流背景音频并开始循环播放",
      "5. 创建 UDP Socket，绑定端口（默认 6000）",
      "6. 广播 HELLO 消息，宣告自身节点信息",
      "7. 启动独立监听线程，接收其他主机的广播消息",
      "8. 等待 3 秒，收集局域网内各主机信息，建立主机列表",
      "9. 按 IP 地址排序，确定屏幕拓扑关系（左邻/右邻）",
      "10. 按配置数量随机生成初始鱼群（默认 5 条）",
      "11. 进入主事件循环（渲染 → 更新 → 通信 → 渲染）"
    ], { width: 6826 })] }),
    new TableRow({ children: [cell("异常事件流", { width: 2200 }), cell([
      "A1. 窗口初始化失败 → 终端输出错误信息并退出程序",
      "A2. 端口被占用 → 递增端口号（6001, 6002...），最多尝试 10 次，均失败则提示用户手动指定",
      "A3. 3 秒内未发现其他主机 → 以单机模式运行，鱼在本机屏幕内反弹游动",
      "A4. 音频文件缺失 → 静默跳过音效模块，系统正常运行但不播放声音"
    ], { width: 6826 })] }),
  ]
});
children.push(uc01Table);

// UC09
children.push(para(""));
children.push(para("用例 UC09：自动组网", { run: { bold: true, size: 26 } }));
children.push(para(""));

const uc09Table = new Table({
  width: { size: 9026, type: WidthType.DXA },
  columnWidths: [2200, 6826],
  rows: [
    new TableRow({ children: [headerCell("项目", 2200), headerCell("说明", 6826)] }),
    new TableRow({ children: [cell("用例编号", { width: 2200 }), cell("UC09", { width: 6826 })] }),
    new TableRow({ children: [cell("用例名称", { width: 2200 }), cell("自动组网", { width: 6826 })] }),
    new TableRow({ children: [cell("参与者", { width: 2200 }), cell("系统（自动执行）", { width: 6826 })] }),
    new TableRow({ children: [cell("前置条件", { width: 2200 }), cell("同局域网内至少 1 台主机已运行本程序，UDP 端口可达", { width: 6826 })] }),
    new TableRow({ children: [cell("后置条件", { width: 2200 }), cell("所有主机建立拓扑关系，确定各自的相邻主机，进入正常运行状态", { width: 6826 })] }),
    new TableRow({ children: [cell("基本事件流", { width: 2200 }), cell([
      "1. 主机 A 启动，通过 UDP 端口广播 HELLO 消息（含 hostname、IP、port）",
      "2. 主机 B 的监听线程收到 HELLO 广播",
      "3. 主机 B 回复 ACK 消息（含自身 hostname、IP、port）",
      "4. 主机 A 收到 ACK，将 B 加入主机列表",
      "5. 主机 A 按 IP 地址升序排列所有已知主机，分配 position 编号",
      "6. 主机 A 广播 TOPOLOGY 消息，通知所有主机拓扑协商结果",
      "7. 各主机根据全局拓扑确定左邻 host_id 和右邻 host_id（首尾主机无左邻/右邻）",
      "8. 组网完成，HUD 显示联机主机数量和自身位置"
    ], { width: 6826 })] }),
    new TableRow({ children: [cell("异常事件流", { width: 2200 }), cell([
      "A1. 心跳超时（10 秒未收到 HEARTBEAT）→ 判定主机离线，从主机列表中移除，触发拓扑重算",
      "A2. 新主机加入（收到新的 HELLO）→ 触发拓扑重算，广播新的 TOPOLOGY 消息通知全网",
      "A3. 收到非法消息（无法解析的乱码）→ 丢弃，记录日志"
    ], { width: 6826 })] }),
  ]
});
children.push(uc09Table);

// UC11
children.push(new Paragraph({ children: [new PageBreak()] }));
children.push(para("用例 UC11：跨屏切换", { run: { bold: true, size: 26 } }));
children.push(para(""));

const uc11Table = new Table({
  width: { size: 9026, type: WidthType.DXA },
  columnWidths: [2200, 6826],
  rows: [
    new TableRow({ children: [headerCell("项目", 2200), headerCell("说明", 6826)] }),
    new TableRow({ children: [cell("用例编号", { width: 2200 }), cell("UC11", { width: 6826 })] }),
    new TableRow({ children: [cell("用例名称", { width: 2200 }), cell("跨屏切换与状态同步", { width: 6826 })] }),
    new TableRow({ children: [cell("参与者", { width: 2200 }), cell("系统（自动执行）", { width: 6826 })] }),
    new TableRow({ children: [cell("前置条件", { width: 2200 }), cell("至少 2 台主机完成组网，鱼群在各主机上正常游动", { width: 6826 })] }),
    new TableRow({ children: [cell("后置条件", { width: 2200 }), cell("越界鱼被目标主机接收并继续游动，源主机正确移除该鱼", { width: 6826 })] }),
    new TableRow({ children: [cell("基本事件流", { width: 2200 }), cell([
      "1. 主机 A 每帧更新鱼位置后检测边界条件",
      "2. 发现鱼 F3 的 x 坐标 > 屏幕宽度（向右越界）",
      "3. 查询拓扑表，找到右邻主机 B 的 IP:Port",
      "4. 将鱼 F3 的状态数据（fish_id, x, y, direction, speed, size, color）序列化为二进制 TRANSFER 消息",
      "5. 通过 UDP 单播（sendto）将消息发送给主机 B",
      "6. 主机 A 从本地鱼列表中移除 F3",
      "7. 主机 B 的监听线程收到 TRANSFER 消息",
      "8. 反序列化消息，校验数据合法性（坐标、速度范围）",
      "9. 校验通过且 fish_id 不重复，在 x = -2（左边界外侧）创建鱼 F3",
      "10. 鱼 F3 在主机 B 的下一帧更新中自然进入屏幕，继续向右游动"
    ], { width: 6826 })] }),
    new TableRow({ children: [cell("异常事件流", { width: 2200 }), cell([
      "A1. 对应方向无相邻主机（如最右侧主机上的鱼向右越界）→ 鱼反弹，方向角反转 180°",
      "A2. UDP 消息丢失（网络丢包）→ 发送端已删除该鱼，接收端无感知，鱼自然消失（允许少量丢失）",
      "A3. 重复消息（UDP 重传导致同一 fish_id 到达两次）→ 接收端按 fish_id 去重，丢弃重复消息",
      "A4. 消息校验失败（数据超出合法范围）→ 丢弃消息，记录警告日志"
    ], { width: 6826 })] }),
  ]
});
children.push(uc11Table);

// ── 2.4 系统数据需求 ──
children.push(new Paragraph({ children: [new PageBreak()] }));
children.push(heading(HeadingLevel.HEADING_2, "2.4  系统数据需求"));

children.push(heading(HeadingLevel.HEADING_3, "2.4.1  数据实体描述"));

children.push(para(""));
children.push(para("1. 鱼实体（Fish Entity）", { run: { bold: true, size: 26 } }));
children.push(para("鱼实体是系统的核心数据对象，每条鱼拥有独立的运动状态和外观属性。"));

const fishTable = new Table({
  width: { size: 9026, type: WidthType.DXA },
  columnWidths: [1800, 1826, 5400],
  rows: [
    new TableRow({ children: [headerCell("属性", 1800), headerCell("类型", 1826), headerCell("说明", 5400)] }),
    new TableRow({ children: [cell("fish_id", { width: 1800 }), cell("uint16 (2B)", { width: 1826 }), cell("全局唯一标识，编码方式：高 8 位为主机编号，低 8 位为主机内序号，范围 0-65535", { width: 5400 })] }),
    new TableRow({ children: [cell("x, y", { width: 1800 }), cell("float32 (4B×2)", { width: 1826 }), cell("屏幕坐标位置（像素），x ∈ [-10, width+10], y ∈ [-10, height+10]", { width: 5400 })] }),
    new TableRow({ children: [cell("direction", { width: 1800 }), cell("float32 (4B)", { width: 1826 }), cell("游动方向角（弧度），范围 0-2π，0 表示向右，π/2 表示向下", { width: 5400 })] }),
    new TableRow({ children: [cell("speed", { width: 1800 }), cell("float16 (2B)", { width: 1826 }), cell("游动速率（像素/秒），范围 50-200，受全局速度倍率影响", { width: 5400 })] }),
    new TableRow({ children: [cell("size", { width: 1800 }), cell("uint8 (1B)", { width: 1826 }), cell("鱼体大小倍率，存储为 uint8（实际值 × 100），范围 50-150（即 0.5-1.5）", { width: 5400 })] }),
    new TableRow({ children: [cell("color", { width: 1800 }), cell("uint8[3] (3B)", { width: 1826 }), cell("RGB 颜色值，每个通道 0-255，在 HSV 空间随机色相后转换保证色彩区分度", { width: 5400 })] }),
    new TableRow({ children: [cell("host_id", { width: 1800 }), cell("uint8 (1B)", { width: 1826 }), cell("当前所在主机的编号（按 IP 排序后的 position 值）", { width: 5400 })] }),
    new TableRow({ children: [cell("state", { width: 1800 }), cell("uint8 (1B)", { width: 1826 }), cell("状态枚举：0=正常游动, 1=越界传输中（预留，用于未来扩展）", { width: 5400 })] }),
  ]
});
children.push(fishTable);

children.push(para("总大小：18 字节（不含 state 为 17 字节）"));

children.push(para(""));
children.push(para("2. 主机节点（Host Node）", { run: { bold: true, size: 26 } }));

const hostTable = new Table({
  width: { size: 9026, type: WidthType.DXA },
  columnWidths: [2200, 1826, 5000],
  rows: [
    new TableRow({ children: [headerCell("属性", 2200), headerCell("类型", 1826), headerCell("说明", 5000)] }),
    new TableRow({ children: [cell("host_id", { width: 2200 }), cell("uint8 (1B)", { width: 1826 }), cell("主机编号，按 IP 地址升序排序后自动分配（0, 1, 2...）", { width: 5000 })] }),
    new TableRow({ children: [cell("hostname", { width: 2200 }), cell("string", { width: 1826 }), cell("主机名称（socket.gethostname()），用于 HUD 显示", { width: 5000 })] }),
    new TableRow({ children: [cell("ip", { width: 2200 }), cell("string / uint32", { width: 1826 }), cell("IPv4 地址，网络传输时转换为 4 字节二进制", { width: 5000 })] }),
    new TableRow({ children: [cell("port", { width: 2200 }), cell("uint16 (2B)", { width: 1826 }), cell("UDP 通信端口号，默认 6000，端口冲突时递增", { width: 5000 })] }),
    new TableRow({ children: [cell("position", { width: 2200 }), cell("uint8 (1B)", { width: 1826 }), cell("屏幕排列位置，从左到右为 0, 1, 2...，同一值代表同一列", { width: 5000 })] }),
    new TableRow({ children: [cell("last_heartbeat", { width: 2200 }), cell("float64 (8B)", { width: 1826 }), cell("最后收到心跳的时间戳（time.time()），用于超时检测", { width: 5000 })] }),
  ]
});
children.push(hostTable);

children.push(para(""));
children.push(para("3. 通信消息（Message）", { run: { bold: true, size: 26 } }));
children.push(para("所有网络消息采用统一二进制格式，定长头部 + 变长载荷："));

children.push(para(""));
children.push(para("消息头部（固定 8 字节）：", { run: { bold: true } }));
children.push(para("[类型 1B] [发送者host_id 1B] [时间戳 4B] [载荷长度 2B]"));
children.push(para("头部采用网络字节序（大端），对应的 Python struct 格式串为 !BBIBH。时间戳为发送时刻的毫秒级 Unix 时间戳（取低 32 位），用于接收端计算跨屏延迟。"));

children.push(para(""));
children.push(para("各消息类型总大小计算：", { run: { bold: true } }));
children.push(bulletItem("HEARTBEAT: 8B（头部）+ 0B（空载荷）= 8 字节"));
children.push(bulletItem("GOODBYE: 8B（头部）+ 0B（空载荷）= 8 字节"));
children.push(bulletItem("HELLO: 8B（头部）+ 1B（hostname 长度）+ 变长 hostname + 4B（IP）+ 2B（port）≈ 8 + 1 + 10 + 4 + 2 = 25 字节"));
children.push(bulletItem("ACK: 同 HELLO，约 25 字节"));
children.push(bulletItem("TOPOLOGY: 8B（头部）+ 1B（主机数量 N）+ N × 2B（host_id + position）≈ 8 + 1 + 10 = 19 字节（以 5 台主机计）"));
children.push(bulletItem("TRANSFER: 8B（头部）+ 20B（载荷: fish_id 2B + x 4B + y 4B + direction 4B + speed 2B + size 1B + color 3B）= 28 字节"));
children.push(para("所有消息均远小于链路层 MTU（1500 字节），不会产生 IP 分片，保证传输效率。"));

children.push(para(""));
children.push(para("消息类型定义：", { run: { bold: true } }));

const msgTable = new Table({
  width: { size: 9026, type: WidthType.DXA },
  columnWidths: [1200, 900, 1626, 5300],
  rows: [
    new TableRow({ children: [headerCell("类型码", 1200), headerCell("名称", 900), headerCell("方向", 1626), headerCell("载荷内容", 5300)] }),
    new TableRow({ children: [cell("0x01", { width: 1200 }), cell("HELLO", { width: 900 }), cell("广播", { width: 1626 }), cell("hostname 长度(1B) + hostname(变长) + IP(4B) + port(2B)", { width: 5300 })] }),
    new TableRow({ children: [cell("0x02", { width: 1200 }), cell("ACK", { width: 900 }), cell("单播", { width: 1626 }), cell("格式同 HELLO，作为对 HELLO 消息的应答", { width: 5300 })] }),
    new TableRow({ children: [cell("0x03", { width: 1200 }), cell("HEARTBEAT", { width: 900 }), cell("广播", { width: 1626 }), cell("空载荷，仅头部，总长 8 字节", { width: 5300 })] }),
    new TableRow({ children: [cell("0x04", { width: 1200 }), cell("TOPOLOGY", { width: 900 }), cell("广播", { width: 1626 }), cell("主机数量(1B) + [host_id(1B) + position(1B)] × N", { width: 5300 })] }),
    new TableRow({ children: [cell("0x05", { width: 1200 }), cell("TRANSFER", { width: 900 }), cell("单播", { width: 1626 }), cell("fish_id(2B) + x(4B) + y(4B) + direction(4B) + speed(2B) + size(1B) + color(3B) = 20B", { width: 5300 })] }),
    new TableRow({ children: [cell("0x06", { width: 1200 }), cell("GOODBYE", { width: 900 }), cell("广播", { width: 1626 }), cell("空载荷，通知其他主机本机即将退出", { width: 5300 })] }),
  ]
});
children.push(msgTable);

children.push(para("单条 TRANSFER 消息总大小 = 8B（头部）+ 20B（载荷）= 28 字节，远小于链路层 MTU（1500 字节），不会产生 IP 分片。"));

children.push(heading(HeadingLevel.HEADING_3, "2.4.2  配置文件数据"));

children.push(para("系统使用 INI 格式配置文件（config.ini），位于程序同级目录，各段定义如下："));

children.push(para(""));
children.push(para("config.ini 内容：", { run: { bold: true } }));
children.push(para(""));
children.push(para("[Display]", { run: { font: "Courier New", size: 20 } }));
children.push(para("width = 800          ; 窗口宽度（像素）", { run: { font: "Courier New", size: 20 } }));
children.push(para("height = 600         ; 窗口高度（像素）", { run: { font: "Courier New", size: 20 } }));
children.push(para("fullscreen = false   ; 是否全屏启动", { run: { font: "Courier New", size: 20 } }));
children.push(para("", { run: { font: "Courier New", size: 20 } }));
children.push(para("[Fish]", { run: { font: "Courier New", size: 20 } }));
children.push(para("count = 5            ; 初始鱼数量（1-20）", { run: { font: "Courier New", size: 20 } }));
children.push(para("speed_multiplier = 1.0 ; 全局速度倍率（0.5-2.0）", { run: { font: "Courier New", size: 20 } }));
children.push(para("", { run: { font: "Courier New", size: 20 } }));
children.push(para("[Network]", { run: { font: "Courier New", size: 20 } }));
children.push(para("port = 6000          ; UDP 通信起始端口", { run: { font: "Courier New", size: 20 } }));
children.push(para("heartbeat_interval = 3  ; 心跳间隔（秒）", { run: { font: "Courier New", size: 20 } }));
children.push(para("heartbeat_timeout = 10  ; 心跳超时（秒）", { run: { font: "Courier New", size: 20 } }));
children.push(para("", { run: { font: "Courier New", size: 20 } }));
children.push(para("[Audio]", { run: { font: "Courier New", size: 20 } }));
children.push(para("enabled = true       ; 启动时是否开启音效", { run: { font: "Courier New", size: 20 } }));
children.push(para("volume = 0.5         ; 音量（0.0-1.0）", { run: { font: "Courier New", size: 20 } }));

children.push(para(""));
children.push(para("配置说明：", { run: { bold: true } }));
children.push(bulletItem("配置文件缺失时，系统使用上述默认值运行，不会因缺少配置文件而启动失败"));
children.push(bulletItem("端口（port）为起始端口，若被占用则自动尝试 port+1、port+2... 最多 10 次，仍失败则报错退出"));
children.push(bulletItem("配置面板中的修改会实时写回 config.ini，下次启动时自动沿用上次的设置"));
children.push(bulletItem("所有尺寸和坐标单位为像素（px），所有时间单位为秒（s）"));

// ── 2.5 系统非功能需求 ──
children.push(new Paragraph({ children: [new PageBreak()] }));
children.push(heading(HeadingLevel.HEADING_2, "2.5  系统非功能需求"));

// 2.5.1
children.push(heading(HeadingLevel.HEADING_3, "2.5.1  性能需求"));

const perfTable = new Table({
  width: { size: 9026, type: WidthType.DXA },
  columnWidths: [2400, 2000, 4626],
  rows: [
    new TableRow({ children: [headerCell("指标", 2400), headerCell("要求", 2000), headerCell("测量/验证方法", 4626)] }),
    new TableRow({ children: [cell("动画帧率", { width: 2400 }), cell("≥ 25 FPS", { width: 2000 }), cell("Pygame clock.get_fps() 实时监控，HUD 显示当前帧率", { width: 4626 })] }),
    new TableRow({ children: [cell("跨屏切换延迟", { width: 2400 }), cell("< 100ms", { width: 2000 }), cell("消息中携带发送时间戳，接收端计算差值（含序列化、网络传输、反序列化）", { width: 4626 })] }),
    new TableRow({ children: [cell("CPU 占用率", { width: 2400 }), cell("< 30%", { width: 2000 }), cell("空闲场景下（5条鱼）通过任务管理器/Activity Monitor 测量", { width: 4626 })] }),
    new TableRow({ children: [cell("内存占用", { width: 2400 }), cell("< 200MB", { width: 2000 }), cell("进程内存监控（psutil 或系统自带工具）", { width: 4626 })] }),
    new TableRow({ children: [cell("启动时间", { width: 2400 }), cell("< 5 秒", { width: 2000 }), cell("从双击程序到窗口正常显示并进入主循环的耗时", { width: 4626 })] }),
    new TableRow({ children: [cell("网络带宽", { width: 2400 }), cell("< 50KB/s 每主机", { width: 2000 }), cell("5条鱼跨屏频率下的估算：每条约 28B × 越界频率（约 0.2次/s/鱼）= 28B/s/鱼", { width: 4626 })] }),
  ]
});
children.push(perfTable);

// 2.5.2
children.push(heading(HeadingLevel.HEADING_3, "2.5.2  安全性"));
children.push(bulletItem("通信范围限制：UDP 通信仅限局域网内，不对外网开放端口，不涉及任何外部网络地址"));
children.push(bulletItem("数据隐私：UDP 消息仅包含鱼的位置、速度等动画状态数据，不传输任何用户个人信息、文件内容或系统信息"));
children.push(bulletItem("缓冲区安全：单条消息大小硬限制为 512 字节（远小于 UDP 理论最大 65507 字节），在 recvfrom 中使用固定 512 字节缓冲区，防止溢出"));
children.push(bulletItem("配置文件安全：配置文件仅包含程序运行参数，无敏感信息，权限设为用户可读写即可"));
children.push(bulletItem("消息校验：接收端反序列化时对所有字段进行合法性校验（坐标范围、速度范围、host_id 有效性），校验失败则丢弃并记录日志"));

// 2.5.3
children.push(heading(HeadingLevel.HEADING_3, "2.5.3  可靠性"));
children.push(bulletItem("连续运行稳定性：系统需连续运行 30 分钟不崩溃（正式演示时长一般为 5-10 分钟，30 分钟留足余量）"));
children.push(bulletItem("UDP 丢包容忍：UDP 协议不保证可靠交付，消息丢失仅导致个别鱼跨屏后消失，不影响整体运行——这是设计取舍，而非 bug"));
children.push(bulletItem("单点故障隔离：单台主机意外退出（断电、程序崩溃等）不影响其他主机继续运行，心跳超时后自动将该主机从拓扑中移除"));
children.push(bulletItem("孤儿鱼处理：主机退出后，曾由该主机持有的鱼自然消失（因为状态仅存在于内存），不会在其他主机上产生异常"));
children.push(bulletItem("心跳超时检测：每 3 秒广播心跳，连续 10 秒未收到某主机心跳即判定离线，自动触发拓扑重算"));
children.push(bulletItem("端口冲突处理：启动时若默认端口 6000 被占用，自动尝试 6001、6002... 最多 10 次"));

// 2.5.4
children.push(heading(HeadingLevel.HEADING_3, "2.5.4  易用性"));
children.push(bulletItem("即开即用：双击启动即可运行，无需手动配置网络或输入 IP 地址——所有组网过程全自动"));
children.push(bulletItem("图形化配置：参数配置面板使用 Pygame 内建 UI（滑块 + 按钮），鱼数量用滑块拖拽（1-20），速度用滑块拖拽（0.5x-2x）"));
children.push(bulletItem("全屏/窗口切换：按 F11 键一键切换窗口模式与全屏模式，适配不同展示场景"));
children.push(bulletItem("音效独立控制：按 M 键一键静音/取消静音，与动画完全解耦"));
children.push(bulletItem("实时状态 HUD：屏幕左上角半透明面板显示联机主机数量、本机鱼数量、实时 FPS，信息简洁不遮挡画面"));
children.push(bulletItem("键盘快捷键总览：F11=全屏切换 | M=静音 | P=暂停/继续 | R=重置鱼群 | Q=退出"));

// 2.5.5
children.push(heading(HeadingLevel.HEADING_3, "2.5.5  可维护性与可扩展性"));
children.push(bulletItem("模块化架构：网络通信（network.py）、动画渲染（renderer.py）、音效（audio.py）、配置管理（config.py）、主循环（main.py）各自独立，通过明确接口交互"));
children.push(bulletItem("通信抽象：网络模块定义 send()、broadcast()、receive() 统一接口，当前实现为 UDP，后续可替换为 TCP 或 WebSocket 而不影响其他模块"));
children.push(bulletItem("鱼行为封装：Fish 类独立管理自身运动逻辑（update、draw、check_boundary），新增行为模式（如躲避、跟随、集群）只需扩展 Fish 类"));
children.push(bulletItem("配置驱动：所有可调参数通过 config.ini 管理，无需修改代码即可调整窗口大小、鱼数量、端口、心跳间隔等"));
children.push(bulletItem("代码注释规范：所有类和公共方法使用 Python docstring（'''...'''），关键算法逻辑添加行内注释"));
children.push(bulletItem("版本控制：使用 Git 进行版本管理，推荐采用 GitHub Classroom 或 Gitee 托管代码"));

// 2.5.6
children.push(heading(HeadingLevel.HEADING_3, "2.5.6  风险因素分析"));

const riskTable = new Table({
  width: { size: 9026, type: WidthType.DXA },
  columnWidths: [2600, 600, 600, 5226],
  rows: [
    new TableRow({ children: [headerCell("风险描述", 2600), headerCell("概率", 600), headerCell("影响", 600), headerCell("应对措施", 5226)] }),
    new TableRow({ children: [cell("队员 Python/Pygame 零基础", { width: 2600 }), cell("中", { width: 600 }), cell("高", { width: 600 }), cell("第一周集中学习：Python socket 编程 + Pygame 基础教程（官方文档 + 示例代码），组长制定学习计划并检查进度", { width: 5226 })] }),
    new TableRow({ children: [cell("跨屏通信延迟达不到 < 100ms", { width: 2600 }), cell("中", { width: 600 }), cell("高", { width: 600 }), cell("优先使用 UDP（非 TCP）避免三次握手延迟；二进制序列化（非 JSON）减小消息体积；在 WiFi 局域网环境下实测验证", { width: 5226 })] }),
    new TableRow({ children: [cell("多机测试环境不便获取", { width: 2600 }), cell("高", { width: 600 }), cell("中", { width: 600 }), cell("开发阶段本机多实例（不同端口号）模拟多屏联动；关键节点借用实验室/机房多台电脑集中联调测试", { width: 5226 })] }),
    new TableRow({ children: [cell("UDP 丢包导致鱼重复/丢失", { width: 2600 }), cell("中", { width: 600 }), cell("中", { width: 600 }), cell("Fish ID 全局唯一 + 接收端去重；设计上允许少量丢包（鱼偶尔消失不影响整体演示效果）", { width: 5226 })] }),
    new TableRow({ children: [cell("Pygame 动画帧率不足（< 25 FPS）", { width: 2600 }), cell("低", { width: 600 }), cell("中", { width: 600 }), cell("使用 Pygame Sprite Group 批量渲染优化；鱼数量上限设为 20 条；减少每帧浮点运算量（使用近似计算）", { width: 5226 })] }),
    new TableRow({ children: [cell("局域网防火墙阻止 UDP 通信", { width: 2600 }), cell("中", { width: 600 }), cell("低", { width: 600 }), cell("在文档中说明需放行 UDP 端口 6000（Windows 防火墙 / macOS 应用防火墙），提供一键添加防火墙规则的脚本", { width: 5226 })] }),
    new TableRow({ children: [cell("队员分工不均，进度不一致", { width: 2600 }), cell("中", { width: 600 }), cell("低", { width: 600 }), cell("按模块分工（网络/动画/音效/配置），每 3 天同步进度，使用 GitHub Issues 跟踪任务，组长及时调整分配", { width: 5226 })] }),
  ]
});
children.push(riskTable);

// ── page setup ──
const doc = new Document({
  styles: {
    default: { document: { run: { font: "Arial", size: 24 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 32, bold: true, font: "Arial" },
        paragraph: { spacing: { before: 360, after: 240 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 28, bold: true, font: "Arial" },
        paragraph: { spacing: { before: 280, after: 200 }, outlineLevel: 1 } },
      { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 26, bold: true, font: "Arial" },
        paragraph: { spacing: { before: 240, after: 160 }, outlineLevel: 2 } },
    ]
  },
  numbering: {
    config: [
      { reference: "bullets",
        levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
      { reference: "numbers",
        levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
      { reference: "overallSteps",
        levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
    ]
  },
  sections: [{
    properties: {
      page: {
        size: { width: 11906, height: 16838 }, // A4
        margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 }
      }
    },
    headers: {
      default: new Header({
        children: [new Paragraph({
          alignment: AlignmentType.RIGHT,
          children: [new TextRun({ text: "局域网多屏联动游鱼动画系统 — 需求分析说明书", font: "Arial", size: 18, color: "999999" })]
        })]
      })
    },
    footers: {
      default: new Footer({
        children: [new Paragraph({
          alignment: AlignmentType.CENTER,
          children: [
            new TextRun({ text: "— ", font: "Arial", size: 18, color: "999999" }),
            new TextRun({ children: [PageNumber.CURRENT], font: "Arial", size: 18, color: "999999" }),
            new TextRun({ text: " —", font: "Arial", size: 18, color: "999999" }),
          ]
        })]
      })
    },
    children
  }]
});

// ── write ──
const outPath = "局域网多屏联动游鱼动画系统—需求分析.docx";
Packer.toBuffer(doc).then(buf => {
  fs.writeFileSync(outPath, buf);
  console.log("✅ Written:", outPath);
  console.log("   Size:", (buf.length / 1024).toFixed(1), "KB");
});
