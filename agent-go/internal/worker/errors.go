package worker

import "strings"

// 标准错误类型，供服务端重试决策（与 backend/app/core/retry.py 对齐）。
const (
	errCommandNotFound       = "COMMAND_NOT_FOUND"
	errPermissionDenied      = "PERMISSION_DENIED"
	errExecutionTimeout      = "AGENT_EXECUTION_TIMEOUT"
	errServiceNotWhitelisted = "SERVICE_NOT_WHITELISTED"
	errTaskActionInvalid     = "TASK_ACTION_INVALID"
	errServiceUnhealthy      = "SERVICE_UNHEALTHY"
	errUnknown               = "UNKNOWN"
)

// classifyFailure 根据执行输出推断标准错误类型。
func classifyFailure(output string) string {
	text := strings.ToLower(output)
	switch {
	case strings.Contains(output, "超时") || strings.Contains(text, "timeout"):
		return errExecutionTimeout
	case strings.Contains(text, "not found") || strings.Contains(text, "no such file") || strings.Contains(text, "unknown service"):
		return errCommandNotFound
	case strings.Contains(text, "permission") || strings.Contains(text, "access denied") || strings.Contains(text, "authentication"):
		return errPermissionDenied
	case strings.Contains(output, "白名单") || strings.Contains(text, "whitelist"):
		return errServiceNotWhitelisted
	case strings.Contains(output, "不允许的操作"):
		return errTaskActionInvalid
	case strings.Contains(text, "failed") || strings.Contains(text, "inactive") || strings.Contains(text, "dead"):
		return errServiceUnhealthy
	default:
		return errUnknown
	}
}
