"""任务错误分类：将执行失败归一到标准 error_type，供服务端重试决策。"""

from __future__ import annotations

COMMAND_NOT_FOUND = "COMMAND_NOT_FOUND"
PERMISSION_DENIED = "PERMISSION_DENIED"
AGENT_EXECUTION_TIMEOUT = "AGENT_EXECUTION_TIMEOUT"
SERVICE_NOT_WHITELISTED = "SERVICE_NOT_WHITELISTED"
TASK_ACTION_INVALID = "TASK_ACTION_INVALID"
SERVICE_UNHEALTHY = "SERVICE_UNHEALTHY"
UNKNOWN = "UNKNOWN"


def classify_failure(output: str | None) -> str:
    """根据执行输出推断标准错误类型。

    Args:
        output: 执行失败时返回的输出文本。

    Returns:
        标准错误类型字符串。
    """
    text = (output or "").lower()
    if "超时" in text or "timeout" in text:
        return AGENT_EXECUTION_TIMEOUT
    if "not found" in text or "not-found" in text or "no such file" in text or "unknown service" in text:
        return COMMAND_NOT_FOUND
    if "permission" in text or "access denied" in text or "authentication" in text:
        return PERMISSION_DENIED
    if "failed" in text or "inactive" in text or "dead" in text:
        return SERVICE_UNHEALTHY
    return UNKNOWN


def classify_validation_error(message: str) -> str:
    """将白名单/操作校验异常归类。"""
    if "白名单" in message or "whitelist" in message.lower():
        return SERVICE_NOT_WHITELISTED
    return TASK_ACTION_INVALID
