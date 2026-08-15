# IOPaint MCP

[English README](README.md)

一个将 [IOPaint](https://github.com/Sanster/IOPaint) REST API 封装为 MCP 工具的自托管服务。

## 这是什么

本项目由两个服务组成：

~~~text
MCP 客户端 / Agent
        |
        | MCP：stdio 或 Streamable HTTP
        v
IOPaint MCP  ---- HTTP/JSON ---->  IOPaint REST 服务
                                      |
                                      v
                              图片擦除、修复和插件
~~~

IOPaint 继续作为独立服务运行，负责真正的图片修复、擦除和插件处理；IOPaint MCP 负责协议适配、图片和 mask 文件读写、区域坐标转 mask，以及调用 IOPaint REST API。

因此你仍然可以同时使用 IOPaint Web UI、IOPaint REST API 和 MCP。

## 适合什么场景

- Agent 已经能够识别图片中的文字或物体，并希望调用 IOPaint 擦除它们。
- OCR 服务能够输出文字坐标，需要自动生成 mask 并修复图片。
- 使用独立的视觉模型或计算机视觉流水线提供待处理区域。
- 用户已经有 mask，只想让 Agent 调用 IOPaint 完成修复。
- 希望把 IOPaint 作为本地服务接入 Codex 或其他 MCP 客户端。
- 希望通过 Docker 同时启动 IOPaint 和 MCP，并选择 CPU 或 NVIDIA CUDA。

## 明确不包含的能力

本项目不包含 OCR、文字检测、目标检测，也不包含独立的视觉模型。这是有意设计的。

外部 OCR、视觉模型或 Agent 负责识别文字/物体，并输出图片像素坐标；本项目负责把坐标变成 mask，再调用 IOPaint 修复区域。

这样可以自由组合：

- 外部 OCR 服务；
- 能看图的 Agent；
- 独立计算机视觉程序；
- 手工提供坐标；
- 手工提供完整 mask。

## MCP 工具

| 工具 | 作用 |
| --- | --- |
| health_check | 检查 MCP 配置的 IOPaint REST 服务是否可访问。 |
| get_server_info | 获取 IOPaint 的服务配置、模型、采样器和插件信息。 |
| list_models | 列出当前 IOPaint 已发现的模型。 |
| switch_model | 切换 IOPaint 进程当前使用的模型。 |
| inpaint_image | 根据已有 mask 修复图片中的白色区域。 |
| create_mask_from_regions | 根据矩形坐标生成黑底白色区域 mask。 |
| erase_regions | 根据矩形坐标生成 mask，并一次性调用 IOPaint 擦除区域。 |
| adjust_mask | 对已有 mask 进行 expand、shrink 或 reverse。 |
| run_plugin_gen_mask | 调用 IOPaint 中可用的 mask 生成插件。 |
| run_plugin_gen_image | 调用 IOPaint 中可用的图片生成插件。 |

MCP 工具的说明中已经明确写入：OCR 由外部提供，mask 中白色像素代表需要编辑的区域，图片路径必须对 MCP 进程可见，IOPaint REST 服务需要先启动。

## 坐标格式

区域坐标使用原图像素坐标系，x 和 y 是矩形左上角：

~~~json
[
  {"x": 120, "y": 80, "width": 260, "height": 48},
  {"x": 120, "y": 150, "width": 180, "height": 42}
]
~~~

create_mask_from_regions 和 erase_regions 会给每个矩形增加 margin，并自动裁剪到图片边界。

生成的 mask：

- 黑色（0）：保留原图；
- 白色（255）：交给 IOPaint 修复。

典型的 Agent 流程：

1. 读取或查看图片。
2. 通过 OCR、视觉能力或用户描述得到文字/物体坐标。
3. 调用 erase_regions。
4. 使用返回的输出图片；如果效果需要调整，可以检查 mask 后重新调用 inpaint_image。

## 依赖

### 本地 Python 部署

- Python 3.10、3.11 或 3.12；
- 一个正在运行的 IOPaint REST 服务；
- 与 CPU 或 CUDA 环境匹配的 PyTorch 和 torchvision；
- mcp[cli] >=1.9 且 <2；
- httpx >=0.27 且 <1；
- Pillow >=9.5 且 <12。

本地启动脚本会安装经过测试的 torch 2.1.2 和 torchvision 0.16.2，然后安装当前项目和 IOPaint。项目本身不会强制固定 PyTorch，因为 CPU 和 CUDA 需要安装不同的 PyTorch wheel。

### Docker 部署

- Docker Desktop 或 Docker Engine；
- Docker Compose v2；
- CPU 部署不需要 NVIDIA 环境；
- CUDA 部署需要 NVIDIA 驱动和 Docker GPU 支持。

CUDA Docker 镜像基于 CUDA 12.1.1，并安装 CUDA 12.1 对应的 PyTorch wheel。

## Windows PowerShell 本地启动

启动脚本会自动：

1. 创建 .venv；
2. 安装对应 CPU/CUDA 版本的 PyTorch；
3. 安装当前项目和 IOPaint；
4. 启动 IOPaint；
5. 等待 IOPaint 完成模型下载并通过健康检查；
6. 再启动 MCP。

~~~powershell
cd D:/git/iopaint-mcp

# CPU
./scripts/start.ps1 -Device cpu -Model lama

# NVIDIA CUDA
./scripts/start.ps1 -Device cuda -Model lama

# 非交互模式；未指定模型时默认使用 lama
./scripts/start.ps1 -Device cpu -NonInteractive
~~~

如果交互式运行时不指定 Model，脚本会让你选择 lama、cv2 或自定义模型名/路径。

默认地址：

- IOPaint Web/API：<http://127.0.0.1:28680>
- MCP Streamable HTTP：<http://127.0.0.1:28681/mcp>

查看日志：

~~~powershell
Get-Content ./runtime/iopaint.log -Wait
Get-Content ./runtime/mcp.log -Wait
~~~

停止本地服务：

~~~powershell
./scripts/stop.ps1
~~~

模型默认保存在 models/，本地 MCP 自动生成的结果默认保存在 runtime/output/。

## Linux/macOS 本地启动

~~~bash
cd /path/to/iopaint-mcp

# CPU
bash ./scripts/start.sh cpu lama

# NVIDIA CUDA
bash ./scripts/start.sh cuda lama

# 停止服务
bash ./scripts/stop.sh
~~~

交互式终端中省略模型参数时，脚本会显示模型选择菜单；非交互终端默认使用 lama。

## 手动本地启动

如果不使用一键脚本，可以自己创建虚拟环境并分别启动两个服务：

~~~powershell
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -e .
./.venv/Scripts/python.exe -m pip install iopaint

# 在另一个终端启动 IOPaint
./.venv/Scripts/iopaint.exe start --model=lama --device=cpu --host=127.0.0.1 --port=28680 --model-dir=./models

# 启动 MCP
$env:IOPAINT_URL = "http://127.0.0.1:28680"
./.venv/Scripts/python.exe -m iopaint_mcp --transport streamable-http --host 127.0.0.1 --port 28681
~~~

调用图片处理工具前，IOPaint REST 服务必须已经运行。

stdio 模式：

~~~powershell
$env:IOPAINT_URL = "http://127.0.0.1:28680"
./.venv/Scripts/python.exe -m iopaint_mcp
~~~

安装后的命令行入口：

~~~powershell
iopaint-mcp --transport streamable-http --host 127.0.0.1 --port 28681
~~~

## Docker 一键部署

Docker 会启动两个容器：

- iopaint：提供 IOPaint REST/Web 服务；
- mcp：提供 MCP Streamable HTTP 服务。

Compose 配置包含健康检查，MCP 会等待 IOPaint 健康后再启动，从而避免首次下载模型时出现 MCP 503 或初始化握手失败。

### Windows PowerShell

~~~powershell
cd D:/git/iopaint-mcp

# CPU，后台运行，首次启动自动构建镜像
./scripts/docker-start.ps1 -Device cpu -Model lama

# NVIDIA CUDA
./scripts/docker-start.ps1 -Device cuda -Model lama

# 前台运行并查看日志
./scripts/docker-start.ps1 -Device cpu -Model lama -Foreground

# 停止 Docker 服务
./scripts/docker-stop.ps1
~~~

### Linux/macOS

~~~bash
# CPU
bash ./scripts/docker-start.sh cpu lama

# NVIDIA CUDA
bash ./scripts/docker-start.sh cuda lama

# 前台运行
DOCKER_FOREGROUND=1 bash ./scripts/docker-start.sh cpu lama

# 停止 Docker 服务
bash ./scripts/docker-stop.sh
~~~

### 直接使用 Docker Compose

一键脚本只是 Docker Compose 的封装，也可以直接使用标准命令。

CPU：

~~~powershell
$env:IOPAINT_MODEL = "lama"
docker compose -p iopaint-mcp -f docker-compose.yml up -d --build
~~~

CUDA：

~~~powershell
$env:IOPAINT_MODEL = "lama"
docker compose -p iopaint-mcp -f docker-compose.yml -f docker-compose.cuda.yml up -d --build
~~~

修改宿主机端口：

~~~powershell
$env:IOPAINT_PORT = "28780"
$env:MCP_PORT = "28781"
docker compose -p iopaint-mcp -f docker-compose.yml up -d --build
~~~

查看状态、日志和停止服务：

~~~powershell
docker compose -p iopaint-mcp ps
docker compose -p iopaint-mcp logs -f
docker compose -p iopaint-mcp down
~~~

默认 Docker 地址：

- IOPaint Web/API：<http://127.0.0.1:28680>
- MCP：<http://127.0.0.1:28681/mcp>

## Docker 文件和路径

Compose 会挂载以下目录：

| 宿主机目录 | 容器目录 | 用途 |
| --- | --- | --- |
| models/ | /models | IOPaint 和 Hugging Face 模型缓存 |
| data/ | /data | 输入、输出和 MCP 可访问的文件 |
| data/input/ | /data/input/ | 建议放置输入图片 |
| outputs/ | /data/output/ | Docker 生成结果在宿主机可见的目录 |
| 宿主机临时目录 | /host-temp | 启用后提供只读的 Agent 临时图片 |

### Agent 附件自动路径桥接

PowerShell 和 shell Docker 启动脚本会自动把宿主机临时目录以只读方式挂载到 /host-temp，并设置 MCP_PATH_MAPPINGS。这样 Agent 可以直接把它拿到的附件路径，例如 C:/Users/me/AppData/Local/Temp/codex-clipboard-image.png，传给 MCP；MCP 会自动将它映射为容器内的 /host-temp/codex-clipboard-image.png。

生成结果会写入 /data/output，该目录挂载到项目的 outputs/ 目录，因此宿主机可以直接看到结果。/host-temp 仍然是只读挂载。直接使用 Docker Compose 时，如果没有显式设置 MCP_HOST_TEMP_DIR 和 MCP_PATH_MAPPINGS，Compose 会自动使用 Windows 的 TEMP 目录；如果要使用自定义临时目录，可以显式配置：

~~~powershell
$env:MCP_HOST_TEMP_DIR = $env:TEMP
$env:MCP_PATH_MAPPINGS = "$env:TEMP=>/host-temp"
docker compose -p iopaint-mcp -f docker-compose.yml up -d --build
~~~

如果没有启用路径桥接，Docker 中调用 MCP 工具时应传入容器内路径，例如：

~~~text
/data/input/photo.png
/data/output/clean.png
~~~

Docker Compose 中的 MCP_ALLOWED_ROOTS 包含 /data 和 /host-temp；临时目录只读挂载，其他宿主机目录不会自动暴露给容器。

## 连接 MCP 客户端

Streamable HTTP 地址：

~~~text
http://127.0.0.1:28681/mcp
~~~

Codex 配置示例：

~~~toml
[mcp_servers.iopaint]
url = "http://127.0.0.1:28681/mcp"
enabled = true
startup_timeout_sec = 120
tool_timeout_sec = 600
~~~

修改配置后，需要重启或重新连接 MCP 客户端。

注意：MCP 地址和 IOPaint REST 地址不是同一个地址。MCP 客户端应连接 28681/mcp，而不是 28680。

## 配置项

| 变量 | 本地默认值 | Docker 中的值 | 说明 |
| --- | --- | --- | --- |
| IOPAINT_URL | http://127.0.0.1:28680 | http://iopaint:8080 | MCP 使用的 IOPaint REST 地址 |
| IOPAINT_MODEL | lama | lama | 启动时选择的模型 |
| IOPAINT_PORT | 28680 | 宿主机映射端口 | IOPaint 宿主机端口 |
| MCP_HOST | 127.0.0.1 | 容器内 0.0.0.0 | MCP 监听地址 |
| MCP_PORT | 28681 | 容器内 8000 | MCP 端口 |
| MCP_OUTPUT_DIR | ./runtime/output | /data/output | 默认输出目录 |
| MCP_HOST_OUTPUT_DIR | 未设置 | 启动脚本自动使用 outputs/ | 工具结果中返回的宿主机可见输出路径 |
| MCP_ALLOWED_ROOTS | 未设置 | /data:/host-temp | 可选的文件访问白名单 |
| MCP_HOST_TEMP_DIR | 未设置 | 启动脚本自动使用宿主机临时目录 | 只读挂载到 /host-temp 的宿主机目录 |
| MCP_PATH_MAPPINGS | 未设置 | 启动脚本自动设置为临时目录=>/host-temp | 外部路径到容器路径的映射，多个映射用分号分隔 |

## MCP 与 IOPaint REST API 的对应关系

本项目是适配层，不是 IOPaint 的替代品。目前使用的接口包括：

| MCP 操作 | IOPaint REST 接口 |
| --- | --- |
| health_check、get_server_info、list_models | GET /api/v1/server-config |
| switch_model | POST /api/v1/model |
| inpaint_image、erase_regions | POST /api/v1/inpaint |
| adjust_mask | POST /api/v1/adjust_mask |
| run_plugin_gen_mask | POST /api/v1/run_plugin_gen_mask |
| run_plugin_gen_image | POST /api/v1/run_plugin_gen_image |

MCP 从本地读取图片和 mask，将其编码为 data URL 后发送给 IOPaint，再将返回的二进制图片写入本地文件。

## 常见问题

### MCP 返回 HTTP 503 或初始化失败

先检查 IOPaint 是否健康：

~~~powershell
Invoke-WebRequest http://127.0.0.1:28680/api/v1/server-config
~~~

第一次启动下载模型可能需要几分钟。可以查看 runtime/iopaint.log，或者执行：

~~~powershell
docker compose logs -f iopaint
~~~

本项目的本地和 Docker 启动流程都会等待 IOPaint 健康后再提供 MCP。

### 端口被占用

启动前设置新的宿主机端口：

~~~powershell
$env:IOPAINT_PORT = "28780"
$env:MCP_PORT = "28781"
~~~

同时把 MCP 客户端配置中的 URL 改成新的 MCP 端口。

### MCP 找不到图片

MCP 进程必须能够访问传入的图片路径。Docker 模式下必须使用 /data/... 路径，并且图片应放在项目的 data/ 目录下。

### CUDA 启动失败

先单独验证 NVIDIA 驱动和 Docker GPU 是否正常。排查 MCP 集成时，可以先使用 CPU 模式确认整个流程没有问题。

## 开发和测试

~~~powershell
python -m pip install -e .
python -m pytest
~~~

当前单元测试主要覆盖 mask 区域生成，不需要下载 IOPaint 模型，也不需要 GPU 服务。

## 项目结构

~~~text
src/iopaint_mcp/       MCP 服务、IOPaint REST 客户端、路径和 mask 工具
scripts/               本地和 Docker 启停脚本
docker/                CPU 和 CUDA Dockerfile
docker-compose*.yml    CPU Compose 配置和 CUDA 覆盖配置
data/                  宿主机输入输出目录
models/                宿主机模型缓存目录
runtime/               本地日志、PID 文件和本地默认输出目录
outputs/               Docker 输出结果目录
tests/                 单元测试
~~~

## 安全说明

默认配置只监听本机地址，适合本地使用。如果要让其他机器访问 MCP 或 IOPaint，请放在可信网络或带认证的反向代理之后。

MCP 进程默认可以读写它能够访问到的路径；可以通过 MCP_ALLOWED_ROOTS 限制文件范围。Docker 普通文件访问范围是 /data，同时将配置的 Agent 临时目录以只读方式挂载到 /host-temp。

本适配器与 IOPaint 是独立项目。关于 IOPaint 的模型、插件、REST API 行为和许可证，请参考 [IOPaint 官方仓库](https://github.com/Sanster/IOPaint)。
