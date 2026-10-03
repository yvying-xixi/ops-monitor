package collector

import (
	"context"
	"strings"
	"time"

	"github.com/yvying-xixi/ops-monitor/agent-go/internal/syscmd"
)

// 服务状态枚举。
const (
	StatusRunning = "RUNNING"
	StatusStopped = "STOPPED"
	StatusFailed  = "FAILED"
	StatusUnknown = "UNKNOWN"
)

// serviceStatusMap 将 systemctl is-active 输出映射为标准枚举。
var serviceStatusMap = map[string]string{
	"active":   StatusRunning,
	"inactive": StatusStopped,
	"failed":   StatusFailed,
}

// ServiceStatus 单个服务状态。
type ServiceStatus struct {
	ServiceName   string `json:"service_name"`
	CurrentStatus string `json:"current_status"`
}

// ServiceCollector 通过 systemctl 采集服务状态。
type ServiceCollector struct {
	Runner  syscmd.Runner
	Timeout time.Duration
}

// NewServiceCollector 创建服务采集器，默认超时 10s。
func NewServiceCollector(runner syscmd.Runner) *ServiceCollector {
	return &ServiceCollector{Runner: runner, Timeout: 10 * time.Second}
}

// isActive 查询单个服务状态并映射为标准枚举。
func (c *ServiceCollector) isActive(service string) string {
	res, err := c.Runner.Run(context.Background(), c.Timeout, "systemctl", "is-active", service)
	if err != nil {
		return StatusUnknown
	}
	output := strings.TrimSpace(strings.ToLower(res.Stdout))
	if res.ExitCode == 0 {
		return StatusRunning
	}
	if mapped, ok := serviceStatusMap[output]; ok {
		return mapped
	}
	return StatusUnknown
}

// Collect 采集一批服务的状态。
func (c *ServiceCollector) Collect(services []string) []ServiceStatus {
	result := make([]ServiceStatus, 0, len(services))
	for _, name := range services {
		result = append(result, ServiceStatus{
			ServiceName:   name,
			CurrentStatus: c.isActive(name),
		})
	}
	return result
}
