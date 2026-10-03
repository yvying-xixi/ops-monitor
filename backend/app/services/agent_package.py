"""Agent 安装包构建：打包 agent 源码/二进制与安装脚本，供平台下载。

支持两种运行时（runtime）：
- `python`：Python 版 Agent（源码 + install.sh + systemd 模板）；
- `go`：Go 版 Agent（预编译二进制 + install.sh + systemd 模板）。

包结构与 `agent*/install.sh` 的布局检测约定一致，便于 `tar xzf && sudo ./install.sh`。
"""

from __future__ import annotations

import io
import tarfile
from pathlib import Path

from app.core.config import settings

# 运行时常量
RUNTIME_PYTHON = "python"
RUNTIME_GO = "go"
SUPPORTED_RUNTIMES = (RUNTIME_PYTHON, RUNTIME_GO)

# 打包时排除的目录/文件名
EXCLUDE_PARTS = {".venv", "__pycache__", "tests", ".pytest_cache", ".git"}
EXCLUDE_FILES = {"config.yaml"}
DEFAULT_VERSION = "1.0.0"
PACKAGE_PREFIX = "ops-agent"


class AgentPackageError(RuntimeError):
    """Agent 安装包构建失败。"""


def normalize_runtime(runtime: str | None) -> str:
    """校验并归一化运行时参数，非法值回退为默认运行时。"""
    if runtime in SUPPORTED_RUNTIMES:
        return runtime
    return RUNTIME_PYTHON


def bundle_root() -> Path:
    """解析 agent 包来源根目录。

    优先使用配置 `AGENT_BUNDLE_DIR`；为空时回退到仓库根（本地开发）。
    该目录下应包含 `agent/`、`agent-go/` 与 `deploy/systemd/`。
    """
    configured = settings.AGENT_BUNDLE_DIR.strip()
    if configured and Path(configured).is_dir():
        return Path(configured)
    # backend/app/services/agent_package.py → parents[3] = 仓库根
    return Path(__file__).resolve().parents[3]


def _agent_dir(root: Path, runtime: str) -> Path:
    """返回指定运行时的 agent 源目录。"""
    return root / ("agent-go" if runtime == RUNTIME_GO else "agent")


def _systemd_file(root: Path, runtime: str) -> Path:
    """返回指定运行时的 systemd 模板路径。"""
    name = "server-agent-go.service" if runtime == RUNTIME_GO else "server-agent.service"
    return root / "deploy" / "systemd" / name


def agent_version(root: Path | None = None, runtime: str = RUNTIME_PYTHON) -> str:
    """读取指定运行时的 agent 版本号。"""
    base = root if root is not None else bundle_root()
    version_file = _agent_dir(base, normalize_runtime(runtime)) / "VERSION"
    if version_file.is_file():
        return version_file.read_text(encoding="utf-8").strip() or DEFAULT_VERSION
    return DEFAULT_VERSION


def read_install_script(runtime: str = RUNTIME_PYTHON) -> str:
    """返回指定运行时的 install.sh 文本内容。"""
    runtime = normalize_runtime(runtime)
    path = _agent_dir(bundle_root(), runtime) / "install.sh"
    if not path.is_file():
        raise AgentPackageError(f"未找到安装脚本: {path}")
    return path.read_text(encoding="utf-8")


def _add_tree(tar: tarfile.TarFile, source: Path, arcname: str) -> None:
    """将目录加入 tar，跳过排除项。"""
    for path in sorted(source.rglob("*")):
        if any(part in EXCLUDE_PARTS for part in path.parts):
            continue
        if path.name in EXCLUDE_FILES:
            continue
        if path.is_dir():
            continue
        tar.add(path, arcname=f"{arcname}/{path.relative_to(source)}")


def _build_python_package(
    root: Path, agent_dir: Path, systemd_file: Path, install_script: Path, version: str
) -> bytes:
    """构建 Python 版安装包（源码）。"""
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
        tar.add(install_script, arcname=f"{PACKAGE_PREFIX}/install.sh")
        info = tarfile.TarInfo(f"{PACKAGE_PREFIX}/VERSION")
        data = (version + "\n").encode("utf-8")
        info.size = len(data)
        tar.addfile(info, io.BytesIO(data))
        _add_tree(tar, agent_dir, f"{PACKAGE_PREFIX}/agent")
        tar.add(systemd_file, arcname=f"{PACKAGE_PREFIX}/deploy/systemd/{systemd_file.name}")
    return buffer.getvalue()


def _build_go_package(
    root: Path, agent_dir: Path, systemd_file: Path, install_script: Path, version: str
) -> bytes:
    """构建 Go 版安装包（预编译二进制 + 配置样例）。"""
    dist_dir = agent_dir / "dist"
    if not dist_dir.is_dir() or not any(dist_dir.glob("ops-agent-*")):
        raise AgentPackageError(
            f"Go Agent 二进制缺失: {dist_dir}。请先运行 agent-go/scripts/build.sh 或从 Release 下载。"
        )
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
        tar.add(install_script, arcname=f"{PACKAGE_PREFIX}/install.sh")
        info = tarfile.TarInfo(f"{PACKAGE_PREFIX}/VERSION")
        data = (version + "\n").encode("utf-8")
        info.size = len(data)
        tar.addfile(info, io.BytesIO(data))
        # 配置样例
        example = agent_dir / "config" / "config.yaml.example"
        if example.is_file():
            tar.add(example, arcname=f"{PACKAGE_PREFIX}/config/config.yaml.example")
        # 二进制（保留 dist 目录结构，install.sh 依赖）
        for binary in sorted(dist_dir.glob("ops-agent-*")):
            tar.add(binary, arcname=f"{PACKAGE_PREFIX}/dist/{binary.name}")
        # systemd 模板
        tar.add(systemd_file, arcname=f"{PACKAGE_PREFIX}/deploy/systemd/{systemd_file.name}")
    return buffer.getvalue()


def build_agent_package(runtime: str = RUNTIME_PYTHON) -> tuple[bytes, str]:
    """构建 agent 安装包（tar.gz）。

    Args:
        runtime: `python`（默认）或 `go`。

    Returns:
        (压缩包字节, 文件名)。

    Raises:
        AgentPackageError: 缺少必要文件。
    """
    runtime = normalize_runtime(runtime)
    root = bundle_root()
    agent_dir = _agent_dir(root, runtime)
    systemd_file = _systemd_file(root, runtime)
    install_script = agent_dir / "install.sh"
    if not agent_dir.is_dir() or not systemd_file.is_file() or not install_script.is_file():
        raise AgentPackageError(f"Agent 包不完整（runtime={runtime}），请检查目录: {root}")

    version = agent_version(root, runtime)
    if runtime == RUNTIME_GO:
        content = _build_go_package(root, agent_dir, systemd_file, install_script, version)
    else:
        content = _build_python_package(root, agent_dir, systemd_file, install_script, version)
    return content, f"{PACKAGE_PREFIX}-{runtime}-{version}.tar.gz"
