# FishMesh

FishMesh 是一个基于 Python、pygame 和 UDP 的局域网多屏联动游鱼演示。它的当前目标是保留原有可视化演示，同时为后续的可靠协议、集群运行时和实验平台建立可测试的 M1 工程基础。

## M1 范围

M1 保留 V1 UDP 协议和现有演示效果，并提供：

- 可安装的 `src` 布局、`fishmesh-demo` 命令和兼容入口 `python src/main.py`；
- 非交互、定时退出的 headless 诊断模式；
- 对损坏数据报、精灵资源路径以及运行时配置的防御性处理；
- 可重试的精灵请求、结构化日志，以及 Windows、macOS、Linux 的 CI 声明矩阵。

Raft、NAT 穿透、二维拓扑、监控仪表板和 V2 协议不在 M1 范围内。

## 架构边界

- `src/fish_demo/` 负责 pygame 生命周期、键鼠输入、渲染集成和 V1 网络消息调度。
- `src/fishmesh/` 放置尽可能与 GUI 解耦的错误、日志、请求跟踪和资源名安全逻辑。
- `src/main.py` 是旧启动方式的兼容层；新的应用入口是 `fish_demo.app:main`。
- 一些平面模块仍保留在 `src/` 下，属于渐进迁移的 legacy 运行时。

## 前置条件

- Python 3.11、3.12 或 3.13（本地默认为 3.12）；
- [uv](https://docs.astral.sh/uv/)；
- 普通启动需要可用的图形环境，三机联动需要三台设备处于同一可广播的 IPv4 局域网。

## 开发环境

```sh
uv sync --extra dev
```

上述命令会根据 `uv.lock` 创建项目虚拟环境并安装开发工具。如果需要可选视频背景支持，再执行 `uv sync --extra dev --extra video`。

## 启动演示

普通启动：

```sh
uv run fishmesh-demo
```

程序会读取 `config.ini`，并在未传 `--expected-hosts` 时询问预期主机数。兼容启动方式是 `uv run python src/main.py`。

Headless 快速冒烟启动（macOS/Linux shell）：

```sh
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy uv run fishmesh-demo --expected-hosts 1 --run-seconds 1 --windowed --no-audio
```

Windows PowerShell：

```powershell
$env:SDL_VIDEODRIVER = "dummy"
$env:SDL_AUDIODRIVER = "dummy"
uv run fishmesh-demo --expected-hosts 1 --run-seconds 1 --windowed --no-audio
```

## 测试与质量命令

```sh
uv run ruff check src/fishmesh src/fish_demo tests scripts
uv run ty check src/fishmesh src/fish_demo
uv run pytest
uv run pytest --cov=src --cov-report=term-missing
uv run python -m compileall -q src
```

当前覆盖率命令如实统计整个 `src/`，包括暂未充分单测的 pygame/legacy 展示模块；项目尚未设定 `fail-under` 阈值。CI 使用相同的 Ruff、ty、pytest coverage 和 headless 冒烟命令。

截至 2026-07-28，本地最终验证的代码快照为
`1843dff986340aaad76d91753e433535e1cc50d6`：208 项测试被收集，207 项通过、
1 项按平台预期跳过，whole-`src` 覆盖率为 62%（2,695 statements，本次
实测 1,018 missed）。远程 Ubuntu/macOS/Windows × Python 3.11/3.12/3.13
矩阵已在 push run `30362449459` 和 PR run `30362452977` 全部通过；真实三台
物理机联调仍待验收。

## 三台局域网设备联调

1. 将三台设备连入同一 IPv4 子网，关闭 AP/client isolation；各机的工程版本、`config.ini` 和需要的 `assets/` 应保持一致。
2. 在三台设备上分别执行 `uv sync --extra dev`，并在系统防火墙中允许 Python/FishMesh 的局域网 UDP 收发。默认发现端口是 6000，端口占用时绑定会在 6000–6009 内后退。
3. 在每台设备上启动 `uv run fishmesh-demo --expected-hosts 3 --port 6000`。最好在较短时间内全部启动，使它们通过 UDP 广播发现对方。
4. 确认每个窗口的 HUD 均看到 3 台主机，再观察鱼从一个屏幕的左/右边界移交到相邻主机。如果发现失败，先检查防火墙、子网广播、无线终端隔离与端口占用。

## 已知限制

- V1 数据报无身份认证、加密、ACK/去重或端到端可靠传输，仅应在可信局域网中演示。
- 广播发现通常不穿越路由器、VLAN 或 NAT，尚无中继/穿透机制。
- 主机 ID 会随拓扑重建而变化；M1 仍使用一维左右相邻关系。
- V1 精灵包没有完整的多帧 manifest；M1 只能保证重试到至少一帧完整保存，无法检测后续缺帧。
- V1 单帧最多为 103,040 字节（224 块 × 每块 460 字节）；导入归一化后超限的 PNG 会被明确拒绝，不会落盘或进入发送循环。
- 网络广告只包含至少有一帧 regular file 且不超过上限的精灵类型；混合目录会保留类型并仅发送合法帧，超限-only 目录不会诱发对端永久重试。
- CI 矩阵已在 Ubuntu、macOS、Windows 上的 Python 3.11–3.13 九个组合全部通过；这不替代真实三台物理机的防火墙、广播和跨屏联调验收。

## Roadmap

设计边界和 M2–M6 后续路线见 [FishMesh 分布式平台设计](docs/superpowers/specs/2026-07-26-fishmesh-distributed-platform-design.md)。M1 的分步实施记录见 [M0–M1 Foundation Plan](docs/superpowers/plans/2026-07-27-fishmesh-m0-m1-foundation.md)。
