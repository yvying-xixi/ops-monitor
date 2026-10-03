package reporter

import (
	"context"
	"encoding/json"
	"time"

	"github.com/yvying-xixi/ops-monitor/agent-go/internal/collector"
)

// 接口路径。
const (
	PathRegister   = "/api/v1/agent/register"
	PathHeartbeat  = "/api/v1/agent/heartbeat"
	PathMetrics    = "/api/v1/agent/metrics"
	PathAssets     = "/api/v1/agent/assets"
	PathServices   = "/api/v1/agent/services"
	PathTasksPend  = "/api/v1/agent/tasks/pending"
	PathTaskResult = "/api/v1/agent/task/result"
)

// utcNowISO 返回 RFC3339 格式的 UTC 时间。
func utcNowISO() string {
	return time.Now().UTC().Format(time.RFC3339)
}

// RegisterResult 注册响应。
type RegisterResult struct {
	ServerID    int64  `json:"server_id"`
	AgentStatus string `json:"agent_status"`
}

// Register 向服务端注册 Agent。
func Register(ctx context.Context, c *Client, serverCode, token string, info collector.SystemInfo, agentVersion string) (*RegisterResult, error) {
	payload := map[string]any{
		"server_code":        serverCode,
		"token":              token,
		"hostname":           info.Hostname,
		"os_name":            info.OSName,
		"os_version":         info.OSVersion,
		"kernel_version":     info.KernelVersion,
		"architecture":       info.Architecture,
		"cpu_model":          info.CPUModel,
		"cpu_cores":          info.CPUCores,
		"memory_total_bytes": info.MemoryTotalBytes,
		"disk_total_bytes":   info.DiskTotalBytes,
		"agent_version":      agentVersion,
	}
	if pk := c.SigningPublicKey(); pk != "" {
		payload["signing_public_key"] = pk
	}
	raw, err := c.Post(ctx, PathRegister, payload)
	if err != nil {
		return nil, err
	}
	var result RegisterResult
	if err := json.Unmarshal(raw, &result); err != nil {
		return nil, &ReporterError{msg: "注册响应解析失败"}
	}
	return &result, nil
}

// SendHeartbeat 发送心跳。
func SendHeartbeat(ctx context.Context, c *Client, serverID int64, agentVersion string) error {
	payload := map[string]any{
		"server_id":     serverID,
		"agent_version": agentVersion,
		"timestamp":     utcNowISO(),
	}
	_, err := c.Post(ctx, PathHeartbeat, payload)
	return err
}

// SendMetrics 上报一轮指标。
func SendMetrics(ctx context.Context, c *Client, serverID int64, m collector.Metrics) error {
	payload := map[string]any{
		"server_id":         serverID,
		"timestamp":         utcNowISO(),
		"cpu_usage":         m.CPUUsage,
		"memory_usage":      m.MemoryUsage,
		"memory_used_bytes": m.MemoryUsedBytes,
		"disk_usage":        m.DiskUsage,
		"network_in_bytes":  m.NetworkInBytes,
		"network_out_bytes": m.NetworkOutBytes,
		"load_1m":           m.Load1m,
		"load_5m":           m.Load5m,
		"load_15m":          m.Load15m,
		"tcp_connections":   m.TCPConnections,
		"uptime_seconds":    m.UptimeSeconds,
	}
	_, err := c.Post(ctx, PathMetrics, payload)
	return err
}

// SendAssets 同步磁盘与网卡资产。
func SendAssets(ctx context.Context, c *Client, serverID int64, disks []collector.DiskAsset, networks []collector.NetworkAsset) error {
	payload := map[string]any{
		"server_id": serverID,
		"timestamp": utcNowISO(),
		"disks":     disks,
		"networks":  networks,
	}
	_, err := c.Post(ctx, PathAssets, payload)
	return err
}

// SendServices 同步服务状态。
func SendServices(ctx context.Context, c *Client, serverID int64, services []collector.ServiceStatus) error {
	payload := map[string]any{
		"server_id": serverID,
		"timestamp": utcNowISO(),
		"services":  services,
	}
	_, err := c.Post(ctx, PathServices, payload)
	return err
}

// PendingTask 待执行任务。
type PendingTask struct {
	ExecutionID   int64  `json:"execution_id"`
	TaskID        int64  `json:"task_id"`
	Action        string `json:"action"`
	ServiceName   string `json:"service_name"`
	TimeoutSecond int    `json:"timeout_seconds"`
}

// FetchPendingTasks 拉取本服务器待执行任务。
func FetchPendingTasks(ctx context.Context, c *Client) ([]PendingTask, error) {
	raw, err := c.Get(ctx, PathTasksPend)
	if err != nil {
		return nil, err
	}
	if len(raw) == 0 || string(raw) == "null" {
		return nil, nil
	}
	var tasks []PendingTask
	if err := json.Unmarshal(raw, &tasks); err != nil {
		return nil, &ReporterError{msg: "待执行任务解析失败"}
	}
	return tasks, nil
}

// TaskResult 任务执行结果回传参数。
type TaskResult struct {
	ExecutionID  int64
	Status       string
	ExitCode     *int
	ResultText   *string
	ErrorMessage *string
	ErrorType    *string
	Logs         *string
}

// ReportTaskResult 回传任务执行结果。
func ReportTaskResult(ctx context.Context, c *Client, r TaskResult) error {
	payload := map[string]any{
		"execution_id":  r.ExecutionID,
		"status":        r.Status,
		"exit_code":     r.ExitCode,
		"result_text":   r.ResultText,
		"error_message": r.ErrorMessage,
		"error_type":    r.ErrorType,
		"logs":          r.Logs,
	}
	_, err := c.Post(ctx, PathTaskResult, payload)
	return err
}
