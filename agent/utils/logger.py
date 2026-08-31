"""Agent 日志工具。"""

from __future__ import annotations

import logging


def setup_logger(level: str = "INFO", file: str | None = None) -> logging.Logger:
    """初始化 Agent 根日志器。

    Args:
        level: 日志级别。
        file: 日志文件路径，为空时输出到标准输出。

    Returns:
        配置完成的根日志器。
    """
    logger = logging.getLogger("agent")
    logger.setLevel(level.upper())
    logger.handlers.clear()

    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s [%(name)s] %(message)s"
    )
    if file:
        handler: logging.Handler = logging.FileHandler(file)
    else:
        handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger
