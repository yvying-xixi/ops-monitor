// Package worker 轮询领取受控服务任务并执行回传。
package worker

import (
	"context"
	"log/slog"
	"time"

	"github.com/yvying-xixi/ops-monitor/agent-go/internal/reporter"
)

// TaskClient 任务相关上报接口，便于测试注入。
type TaskClient interface {
	FetchPendingTasks(ctx context.Context) ([]reporter.PendingTask, error)
	ReportTaskResult(ctx context.Context, r reporter.TaskResult) error
}

// ReporterClient 将 reporter.Client 适配为 TaskClient。
type ReporterClient struct {
	Client *reporter.Client
}

// FetchPendingTasks 实现 TaskClient。
func (r ReporterClient) FetchPendingTasks(ctx context.Context) ([]reporter.PendingTask, error) {
	return reporter.FetchPendingTasks(ctx, r.Client)
}

// ReportTaskResult 实现 TaskClient。
func (r ReporterClient) ReportTaskResult(ctx context.Context, res reporter.TaskResult) error {
	return reporter.ReportTaskResult(ctx, r.Client, res)
}

// ActionExecutor 任务执行接口。
type ActionExecutor interface {
	RunAction(ctx context.Context, service, action string, timeout time.Duration) (bool, string)
	FetchLogs(ctx context.Context, service string, lines int) (bool, string)
}

// Worker 任务执行循环。
type Worker struct {
	client   TaskClient
	executor ActionExecutor
	interval time.Duration
	logger   *slog.Logger
}

// New 创建任务 Worker。
func New(client TaskClient, exec ActionExecutor, interval time.Duration, logger *slog.Logger) *Worker {
	if interval <= 0 {
		interval = 5 * time.Second
	}
	if logger == nil {
		logger = slog.Default()
	}
	return &Worker{client: client, executor: exec, interval: interval, logger: logger}
}

// Run 常驻执行循环，直到 ctx 取消。
func (w *Worker) Run(ctx context.Context) {
	for {
		if ctx.Err() != nil {
			return
		}
		if _, err := w.PollOnce(ctx); err != nil {
			w.logger.Warn("任务轮询失败", "err", err)
		}
		select {
		case <-ctx.Done():
			return
		case <-time.After(w.interval):
		}
	}
}

// PollOnce 执行一轮拉取与处理，返回处理的任务数。
func (w *Worker) PollOnce(ctx context.Context) (int, error) {
	tasks, err := w.client.FetchPendingTasks(ctx)
	if err != nil {
		return 0, err
	}
	processed := 0
	for _, task := range tasks {
		if err := w.executeOne(ctx, task); err != nil {
			w.logger.Error("执行任务异常", "execution_id", task.ExecutionID, "err", err)
			continue
		}
		processed++
	}
	return processed, nil
}

// executeOne 执行单个任务并回传结果。
func (w *Worker) executeOne(ctx context.Context, task reporter.PendingTask) error {
	timeout := time.Duration(task.TimeoutSecond) * time.Second
	if timeout <= 0 {
		timeout = 60 * time.Second
	}

	// 非白名单/非法操作由 executor 返回失败文本。
	if task.Action == "LOGS" {
		success, output := w.executor.FetchLogs(ctx, task.ServiceName, 0)
		return w.report(ctx, task.ExecutionID, success, output, false)
	}

	success, output := w.executor.RunAction(ctx, task.ServiceName, task.Action, timeout)
	return w.report(ctx, task.ExecutionID, success, output, false)
}

// report 根据执行结果回传任务结果。
func (w *Worker) report(ctx context.Context, executionID int64, success bool, output string, _ bool) error {
	result := reporter.TaskResult{ExecutionID: executionID}
	if success {
		result.Status = "SUCCESS"
		result.ResultText = &output
		zero := 0
		result.ExitCode = &zero
		result.Logs = &output
	} else {
		result.Status = "FAILED"
		result.ErrorMessage = &output
		errorType := classifyFailure(output)
		result.ErrorType = &errorType
	}
	return w.client.ReportTaskResult(ctx, result)
}
