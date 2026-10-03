// Package executor 执行受控服务操作（systemctl）与日志抓取（journalctl）。
//
// 安全约束：服务名须在白名单内、操作类型受限、命令一律以参数列表调用，绝不拼接 shell。
package executor

import (
	"context"
	"errors"
	"fmt"
	"strings"
	"time"

	"github.com/yvying-xixi/ops-monitor/agent-go/internal/syscmd"
)

// 允许的操作类型。
var allowedActions = map[string]bool{
	"STATUS":  true,
	"START":   true,
	"STOP":    true,
	"RESTART": true,
}

// actionCommands 操作到 systemctl 子命令的映射。
var actionCommands = map[string]string{
	"STATUS":  "is-active",
	"START":   "start",
	"STOP":    "stop",
	"RESTART": "restart",
}

// defaultLogLines 日志抓取默认行数。
const defaultLogLines = 200

// Executor 服务执行器。
type Executor struct {
	allowed []string
	runner  syscmd.Runner
}

// New 创建执行器。
func New(allowedServices []string, runner syscmd.Runner) *Executor {
	return &Executor{allowed: allowedServices, runner: runner}
}

// IsAllowed 判断服务是否在白名单内。
func (e *Executor) IsAllowed(service string) bool {
	for _, s := range e.allowed {
		if s == service {
			return true
		}
	}
	return false
}

// Validate 校验服务名与操作类型。
func (e *Executor) Validate(service, action string) error {
	if !e.IsAllowed(service) {
		return fmt.Errorf("服务 %s 不在白名单内，拒绝执行", service)
	}
	if !allowedActions[action] {
		return fmt.Errorf("不允许的操作类型: %s", action)
	}
	return nil
}

// RunAction 执行受控操作，返回 (是否成功, 输出文本)。
func (e *Executor) RunAction(ctx context.Context, service, action string, timeout time.Duration) (bool, string) {
	if err := e.Validate(service, action); err != nil {
		return false, err.Error()
	}
	if timeout <= 0 {
		timeout = 60 * time.Second
	}
	res, err := e.runner.Run(ctx, timeout, "systemctl", actionCommands[action], service)
	if err != nil {
		if errors.Is(err, context.DeadlineExceeded) {
			return false, fmt.Sprintf("执行超时（%ds）", int(timeout.Seconds()))
		}
		return false, fmt.Sprintf("执行失败: %v", err)
	}
	success := res.ExitCode == 0
	var output string
	if success {
		output = strings.TrimSpace(res.Stdout)
	} else {
		output = strings.TrimSpace(res.Stderr)
		if output == "" {
			output = strings.TrimSpace(res.Stdout)
		}
	}
	return success, output
}

// FetchLogs 抓取服务最近日志。
func (e *Executor) FetchLogs(ctx context.Context, service string, lines int) (bool, string) {
	if err := e.Validate(service, "STATUS"); err != nil {
		return false, err.Error()
	}
	if lines <= 0 {
		lines = defaultLogLines
	}
	res, err := e.runner.Run(ctx, 30*time.Second, "journalctl", "-n", fmt.Sprintf("%d", lines), "-u", service, "--no-pager")
	if err != nil {
		return false, fmt.Sprintf("获取日志失败: %v", err)
	}
	out := strings.TrimSpace(res.Stdout)
	if out == "" {
		out = strings.TrimSpace(res.Stderr)
	}
	if res.ExitCode != 0 {
		return false, out
	}
	return true, out
}
