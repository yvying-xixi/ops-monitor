"""任务重试策略：错误分类与退避计算。

职责边界（详见 docs/architecture/task-retry-strategy.md）：
- Agent 网络层负责单次请求的瞬时失败重试（传输层）。
- 本模块服务于 Server 任务层：判断一次失败的尝试是否值得重新调度。

保守原则：无法识别的错误默认**不重试**，避免对参数/权限类错误反复执行。
"""

from __future__ import annotations

RETRYABLE_ERROR_TYPES = frozenset(
    {
        "NETWORK_ERROR",
        "AGENT_OFFLINE",
        "AGENT_TIMEOUT",
        "SERVER_5XX",
    }
)

NON_RETRYABLE_ERROR_TYPES = frozenset(
    {
        "INVALID_ARGUMENT",
        "PERMISSION_DENIED",
        "COMMAND_NOT_FOUND",
        "SERVICE_NOT_WHITELISTED",
        "TASK_ACTION_INVALID",
    }
)

CONDITIONAL_ERROR_TYPES = frozenset(
    {
        "AGENT_EXECUTION_TIMEOUT",
        "SERVICE_UNHEALTHY",
        "DEPENDENCY_UNAVAILABLE",
        "RESOURCE_EXHAUSTED",
    }
)

UNKNOWN_ERROR_TYPE = "UNKNOWN"

BACKOFF_SECONDS = (5, 10, 30, 60)


def classify_error(error_type: str | None, error_message: str | None = None) -> str:
    """将上报的错误归一到标准 error_type。

    Args:
        error_type: Agent 上报的错误类型，可为空。
        error_message: 错误信息，用于在缺少 error_type 时兜底推断。

    Returns:
        标准错误类型字符串。
    """
    if error_type:
        return error_type
    text = (error_message or "").lower()
    if "timeout" in text or "超时" in text:
        return "AGENT_TIMEOUT"
    if any(token in text for token in ("network", "connection", "refused", "unreachable")) or "网络" in text:
        return "NETWORK_ERROR"
    if "offline" in text or "离线" in text:
        return "AGENT_OFFLINE"
    return UNKNOWN_ERROR_TYPE


def is_retryable(error_type: str | None, error_message: str | None = None) -> bool:
    """判断错误是否允许 Server 任务级重试。"""
    return classify_error(error_type, error_message) in RETRYABLE_ERROR_TYPES


def backoff_seconds(attempt: int) -> int:
    """按尝试次数返回退避秒数（指数退避上限封顶）。

    Args:
        attempt: 已完成的尝试编号，从 1 开始。

    Returns:
        下一次重试前应等待的秒数。
    """
    index = max(0, min(attempt - 1, len(BACKOFF_SECONDS) - 1))
    return BACKOFF_SECONDS[index]
