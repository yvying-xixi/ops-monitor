// Package syscmd 提供带超时、禁用 shell 的命令执行抽象。
//
// 通过 Runner 接口注入，便于单元测试替换真实 systemctl/journalctl 调用。
package syscmd

import (
	"bytes"
	"context"
	"errors"
	"os/exec"
	"time"
)

// Result 命令执行结果。
type Result struct {
	Stdout   string
	Stderr   string
	ExitCode int
}

// Runner 命令执行抽象。
type Runner interface {
	// Run 执行命令并返回结果。超时或启动失败返回 error；
	// 非零退出码通过 Result.ExitCode 表达，不视为 error。
	Run(ctx context.Context, timeout time.Duration, name string, args ...string) (Result, error)
}

// ExecRunner 基于 os/exec 的实现，始终以参数列表调用，绝不经过 shell。
type ExecRunner struct{}

// Run 执行命令。
func (ExecRunner) Run(ctx context.Context, timeout time.Duration, name string, args ...string) (Result, error) {
	if timeout > 0 {
		var cancel context.CancelFunc
		ctx, cancel = context.WithTimeout(ctx, timeout)
		defer cancel()
	}
	cmd := exec.CommandContext(ctx, name, args...)
	var stdout, stderr bytes.Buffer
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr
	err := cmd.Run()
	res := Result{Stdout: stdout.String(), Stderr: stderr.String()}
	if err != nil {
		var exitErr *exec.ExitError
		if errors.As(err, &exitErr) {
			res.ExitCode = exitErr.ExitCode()
			return res, nil
		}
		// 上下文超时/取消：返回上下文错误，便于调用方区分超时。
		if ctxErr := ctx.Err(); ctxErr != nil {
			return res, ctxErr
		}
		return res, err
	}
	res.ExitCode = 0
	return res, nil
}
