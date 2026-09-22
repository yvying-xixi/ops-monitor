"""Agent 安装包构建：打包 agent 源码与安装脚本，供平台下载。"""

from __future__ import annotations

import io
import tarfile
from pathlib import Path

from app.core.config import settings

# 打包时排除的目录/文件名
EXCLUDE_PARTS = {".venv", "__pycache__", "tests", ".pytest_cache"}
EXCLUDE_FILES = {"config.yaml"}
DEFAULT_VERSION = "1.0.0"
PACKAGE_PREFIX = "ops-agent"


class AgentPackageError(RuntimeError):
    """Agent 安装包构建失败。"""


def bundle_root() -> Path:
    """解析 agent 包来源根目录。

    优先使用配置 `AGENT_BUNDLE_DIR`；为空时回退到仓库根（本地开发）。
    该目录下应包含 `agent/` 与 `deploy/systemd/server-agent.service`。
    """
    configured = settings.AGENT_BUNDLE_DIR.strip()
    if configured and Path(configured).is_dir():
        return Path(configured)
    # backend/app/services/agent_package.py → parents[3] = 仓库根
    return Path(__file__).resolve().parents[3]


def agent_version() -> str:
    """读取 agent 版本号。"""
    version_file = bundle_root() / "agent" / "VERSION"
    if version_file.is_file():
        return version_file.read_text(encoding="utf-8").strip() or DEFAULT_VERSION
    return DEFAULT_VERSION


def read_install_script() -> str:
    """返回 install.sh 文本内容。"""
    path = bundle_root() / "agent" / "install.sh"
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


def build_agent_package() -> tuple[bytes, str]:
    """构建 agent 安装包（tar.gz）。

    Returns:
        (压缩包字节, 文件名)。

    Raises:
        AgentPackageError: 缺少必要文件。
    """
    root = bundle_root()
    agent_dir = root / "agent"
    systemd_file = root / "deploy" / "systemd" / "server-agent.service"
    install_script = agent_dir / "install.sh"
    if not agent_dir.is_dir() or not systemd_file.is_file() or not install_script.is_file():
        raise AgentPackageError(f"Agent 包不完整，请检查目录: {root}")

    version = agent_version()
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
        # install.sh 置于包根，便于 `tar xzf && sudo ./install.sh`
        tar.add(install_script, arcname=f"{PACKAGE_PREFIX}/install.sh")
        # VERSION
        info = tarfile.TarInfo(f"{PACKAGE_PREFIX}/VERSION")
        data = (version + "\n").encode("utf-8")
        info.size = len(data)
        tar.addfile(info, io.BytesIO(data))
        # agent 源码
        _add_tree(tar, agent_dir, f"{PACKAGE_PREFIX}/agent")
        # systemd 模板
        tar.add(systemd_file, arcname=f"{PACKAGE_PREFIX}/deploy/systemd/server-agent.service")

    return buffer.getvalue(), f"{PACKAGE_PREFIX}-{version}.tar.gz"
