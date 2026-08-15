# IOPaint MCP

An MCP adapter for the IOPaint REST API.

[中文说明 / Chinese guide](README_ZH.md)

## Overview

This repository runs an MCP server in front of a separate IOPaint REST service:

~~~text
MCP client or Agent
        |
        | MCP: stdio or Streamable HTTP
        v
IOPaint MCP  ---- HTTP/JSON ---->  IOPaint REST service
                                      |
                                      v
                              Inpainting and plugins
~~~

The MCP server accepts local image paths, mask paths, and externally detected regions. It converts those inputs into IOPaint REST requests and saves returned images or masks to local paths. IOPaint remains an independent service, so its Web UI and REST API can still be used directly.

## What this repository provides

- A Python MCP server for IOPaint.
- Streamable HTTP for clients such as Codex, and stdio for clients that launch local processes.
- Inpainting from an existing mask.
- Rectangle-to-mask conversion for externally supplied coordinates.
- One-call region erasing: create a mask from rectangles and inpaint the regions.
- Mask expansion, shrinking, and inversion through IOPaint.
- Access to supported IOPaint plugins for mask and image generation.
- Model discovery, model switching, backend health checks, and capability inspection.
- Windows PowerShell, Linux/macOS shell, CPU Docker, and CUDA Docker startup paths.

## What it does not provide

This project does not contain OCR, text detection, object detection, or a vision model. That is intentional.

An OCR service, vision model, or agent can detect text or objects and return image-pixel rectangles. This MCP server turns those rectangles into masks and asks IOPaint to repair the selected area. It can therefore be used with an external OCR service, an image-capable agent, a computer-vision pipeline, or manually selected regions.

## MCP tools

| Tool | Purpose |
| --- | --- |
| health_check | Check whether the configured IOPaint REST service is reachable. |
| get_server_info | Return IOPaint server configuration, models, samplers, and plugins. |
| list_models | List models discovered by the running IOPaint instance. |
| switch_model | Switch the shared active IOPaint model. |
| inpaint_image | Inpaint white regions of an existing mask. |
| create_mask_from_regions | Create a white-on-black mask from rectangles. |
| erase_regions | Create a mask from rectangles and inpaint it in one call. |
| adjust_mask | Expand, shrink, or reverse an existing mask through IOPaint. |
| run_plugin_gen_mask | Run an available IOPaint mask-generation plugin. |
| run_plugin_gen_image | Run an available IOPaint image-generation plugin. |

The MCP server includes tool descriptions explaining that OCR is external, masks use white pixels for edited areas, and paths must be visible to the MCP process.

## Region format

Region coordinates use the source image's pixel coordinate system. x and y are the top-left corner:

~~~json
[
  {"x": 120, "y": 80, "width": 260, "height": 48},
  {"x": 120, "y": 150, "width": 180, "height": 42}
]
~~~

create_mask_from_regions and erase_regions add a configurable margin around every rectangle and clip it to the image boundaries. The generated mask is black for preserved pixels and white (255) for pixels sent to IOPaint.

Typical agent workflow:

1. Read or inspect the image.
2. Obtain text or object rectangles from OCR, vision, or the user.
3. Call erase_regions with those rectangles.
4. Use the returned output path, or inspect the mask and call inpaint_image again with adjusted parameters.

## Dependencies

### Local Python installation

- Python >=3.10 and <3.13.
- A running IOPaint REST service.
- PyTorch and torchvision compatible with the selected CPU or CUDA device.
- mcp[cli] >=1.9 and <2.
- httpx >=0.27 and <1.
- Pillow >=9.5 and <12.

The local startup scripts install the tested combination torch 2.1.2 and torchvision 0.16.2, then install this project and IOPaint. The project package does not force a PyTorch build so CPU and CUDA installations can use different wheels.

### Docker installation

- Docker Desktop or Docker Engine.
- Docker Compose v2.
- For CUDA: a working NVIDIA driver and Docker GPU support. The CUDA image uses CUDA 12.1.1 and installs the CUDA 12.1 PyTorch wheels.

## Local quick start: Windows PowerShell

The script creates .venv when necessary, installs dependencies, starts IOPaint, waits for its REST health endpoint, and only then starts MCP. This wait matters because the first IOPaint launch may need to download a model.

~~~powershell
cd D:/git/iopaint-mcp

# CPU
./scripts/start.ps1 -Device cpu -Model lama

# NVIDIA CUDA
./scripts/start.ps1 -Device cuda -Model lama

# Non-interactive mode; defaults to lama when no model is supplied
./scripts/start.ps1 -Device cpu -NonInteractive
~~~

If Model is omitted in an interactive PowerShell session, the script offers lama, cv2, and a custom model name or path. The default model is lama.

Default endpoints:

- IOPaint REST/Web UI: http://127.0.0.1:28680
- MCP Streamable HTTP: http://127.0.0.1:28681/mcp

View local logs:

~~~powershell
Get-Content ./runtime/iopaint.log -Wait
Get-Content ./runtime/mcp.log -Wait
~~~

Stop local services:

~~~powershell
./scripts/stop.ps1
~~~

The local script stores downloaded models under models/ and generated files under runtime/output/ by default.

## Local quick start: Linux or macOS

~~~bash
cd /path/to/iopaint-mcp

# CPU
bash ./scripts/start.sh cpu lama

# NVIDIA CUDA
bash ./scripts/start.sh cuda lama

# Stop services
bash ./scripts/stop.sh
~~~

Without a model argument, the script offers interactive model selection when a terminal is available. In a non-interactive terminal it defaults to lama.

## Manual local startup

If you do not want to use helper scripts, install the package in a Python 3.10+ virtual environment and start IOPaint separately:

~~~powershell
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -e .
./.venv/Scripts/python.exe -m pip install iopaint

# Start IOPaint in another terminal
./.venv/Scripts/iopaint.exe start --model=lama --device=cpu --host=127.0.0.1 --port=28680 --model-dir=./models

# Start MCP
$env:IOPAINT_URL = "http://127.0.0.1:28680"
./.venv/Scripts/python.exe -m iopaint_mcp --transport streamable-http --host 127.0.0.1 --port 28681
~~~

The IOPaint REST service must be running before image-editing tools are called. For a client that supports stdio:

~~~powershell
$env:IOPAINT_URL = "http://127.0.0.1:28680"
./.venv/Scripts/python.exe -m iopaint_mcp
~~~

The installed console entry point is also available:

~~~powershell
iopaint-mcp --transport streamable-http --host 127.0.0.1 --port 28681
~~~

## Docker one-command deployment

Docker runs IOPaint and MCP as separate services. The MCP container waits for the IOPaint health check before it starts accepting requests.

### Windows PowerShell helper

~~~powershell
cd D:/git/iopaint-mcp

# CPU, detached mode, builds images on the first run
./scripts/docker-start.ps1 -Device cpu -Model lama

# NVIDIA CUDA
./scripts/docker-start.ps1 -Device cuda -Model lama

# Foreground mode
./scripts/docker-start.ps1 -Device cpu -Model lama -Foreground

# Stop Docker services
./scripts/docker-stop.ps1
~~~

### Linux/macOS helper

~~~bash
# CPU
bash ./scripts/docker-start.sh cpu lama

# NVIDIA CUDA
bash ./scripts/docker-start.sh cuda lama

# Foreground mode
DOCKER_FOREGROUND=1 bash ./scripts/docker-start.sh cpu lama

# Stop Docker services
bash ./scripts/docker-stop.sh
~~~

### Direct Docker Compose commands

The helper scripts are optional wrappers around Docker Compose:

~~~powershell
# CPU
$env:IOPAINT_MODEL = "lama"
docker compose -p iopaint-mcp -f docker-compose.yml up -d --build

# CUDA
$env:IOPAINT_MODEL = "lama"
docker compose -p iopaint-mcp -f docker-compose.yml -f docker-compose.cuda.yml up -d --build
~~~

Change host ports if the defaults are occupied:

~~~powershell
$env:IOPAINT_PORT = "28780"
$env:MCP_PORT = "28781"
docker compose -p iopaint-mcp -f docker-compose.yml up -d --build
~~~

Inspect or stop the project:

~~~powershell
docker compose -p iopaint-mcp ps
docker compose -p iopaint-mcp logs -f
docker compose -p iopaint-mcp down
~~~

Default Docker endpoints:

- IOPaint REST/Web UI: http://127.0.0.1:28680
- MCP Streamable HTTP: http://127.0.0.1:28681/mcp

## Docker data and paths

| Host directory | Container directory | Purpose |
| --- | --- | --- |
| models/ | /models | IOPaint and Hugging Face model cache |
| data/ | /data | Input, output, and MCP-accessible files |
| data/input/ | /data/input/ | Suggested input image directory |
| outputs/ | /data/output/ | Host-visible generated output directory |
| Host temporary directory | /host-temp | Read-only desktop-agent attachments when enabled by the helper |

### Desktop-agent attachments

The PowerShell and shell Docker helpers automatically mount the host temporary directory read-only at /host-temp and configure MCP_PATH_MAPPINGS. They also map the repository data directory to /data. This allows a desktop agent to pass an attachment path such as C:/Users/me/AppData/Local/Temp/codex-clipboard-image.png directly to an MCP tool, and to use a host data/output path when needed. MCP translates these paths inside the container.

Generated files are written under /data/output, which is mounted to the repository outputs/ directory. Docker Compose automatically uses the Windows TEMP directory when MCP_HOST_TEMP_DIR and MCP_PATH_MAPPINGS are not set. For a custom temporary directory, configure the bridge explicitly:

~~~powershell
$env:MCP_HOST_TEMP_DIR = $env:TEMP
$env:MCP_PATH_MAPPINGS = "$env:TEMP=>/host-temp"
docker compose -p iopaint-mcp -f docker-compose.yml up -d --build
~~~

On systems where the helper is not used, pass container-visible paths such as /data/input/photo.png, or configure an explicit mapping. MCP_ALLOWED_ROOTS includes /data and /host-temp in the Docker Compose configuration; the temporary directory is mounted read-only.

## Connecting an MCP client

For Streamable HTTP clients, use:

~~~text
http://127.0.0.1:28681/mcp
~~~

For Codex:

~~~toml
[mcp_servers.iopaint]
url = "http://127.0.0.1:28681/mcp"
enabled = true
startup_timeout_sec = 120
tool_timeout_sec = 600
~~~

Reconnect the MCP client after changing its configuration. The MCP endpoint is not the IOPaint REST endpoint; clients should connect to /mcp on port 28681.

## Configuration

| Variable | Local default | Docker value | Description |
| --- | --- | --- | --- |
| IOPAINT_URL | http://127.0.0.1:28680 | http://iopaint:8080 | IOPaint REST base URL used by MCP |
| IOPAINT_MODEL | lama | lama | Model selected at startup |
| IOPAINT_PORT | 28680 | host-published port | IOPaint host port |
| MCP_HOST | 127.0.0.1 | 0.0.0.0 inside container | MCP bind address |
| MCP_PORT | 28681 | 8000 inside container | MCP port |
| MCP_OUTPUT_DIR | ./runtime/output | /data/output | Default output directory |
| MCP_HOST_OUTPUT_DIR | not set | host outputs/ directory from helper | Host-visible output path returned in tool results |
| MCP_ALLOWED_ROOTS | unset | /data:/host-temp | Optional path allow-list |
| MCP_HOST_TEMP_DIR | not set | host temp directory from helper | Host directory mounted read-only at /host-temp |
| MCP_PATH_MAPPINGS | not set | host temp=>/host-temp from helper | External-to-container path mappings separated by semicolons |

## REST API mapping

This project is an adapter, not a replacement for IOPaint. It currently uses:

| MCP operation | IOPaint REST endpoint |
| --- | --- |
| health_check, get_server_info, list_models | GET /api/v1/server-config |
| switch_model | POST /api/v1/model |
| inpaint_image, erase_regions | POST /api/v1/inpaint |
| adjust_mask | POST /api/v1/adjust_mask |
| run_plugin_gen_mask | POST /api/v1/run_plugin_gen_mask |
| run_plugin_gen_image | POST /api/v1/run_plugin_gen_image |

Images and masks are read from local files, encoded as data URLs for the REST request, and binary responses are written back to local files.

## Troubleshooting

### MCP returns HTTP 503 or fails during initialization

Check IOPaint health:

~~~powershell
Invoke-WebRequest http://127.0.0.1:28680/api/v1/server-config
~~~

The first model download can take several minutes. Check runtime/iopaint.log, or run docker compose logs -f iopaint for Docker. The provided local and Docker flows wait for IOPaint health before MCP is made available.

### A port is already in use

Use different host ports:

~~~powershell
$env:IOPAINT_PORT = "28780"
$env:MCP_PORT = "28781"
~~~

The MCP client URL must use the new MCP port.

### MCP cannot find an image

The path must be readable by the MCP process. With Docker, use /data/... paths and place files below the repository data/ directory.

### CUDA does not start

Verify the NVIDIA driver and Docker GPU support independently. CPU mode is a useful fallback for validating the MCP integration.

## Development

~~~powershell
python -m pip install -e .
python -m pytest
~~~

The unit tests cover mask construction and do not require downloading an IOPaint model or starting a GPU service.

## Project layout

~~~text
src/iopaint_mcp/       MCP server, IOPaint REST client, path and mask helpers
scripts/               Local and Docker start/stop helpers
docker/                CPU and CUDA Dockerfiles
docker-compose*.yml    CPU Compose file and CUDA override
data/                  Host-mounted input and output files
models/                Host-mounted model cache
runtime/               Local logs, pid files, and default local outputs
outputs/               Host-visible Docker outputs
tests/                 Unit tests
~~~

## Security and upstream

The default configuration binds services to localhost for local use. If you expose MCP or IOPaint to another machine, put them behind an authenticated and trusted network boundary. The MCP server can read and write any path visible to its process unless MCP_ALLOWED_ROOTS is configured. Docker limits normal access to /data and mounts the configured desktop-agent temporary directory read-only at /host-temp.

This adapter is separate from IOPaint. See the upstream [IOPaint repository](https://github.com/Sanster/IOPaint) for IOPaint models, plugins, REST API behavior, and license information.
