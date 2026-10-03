package worker

import (
	"context"
	"errors"
	"testing"
	"time"

	"github.com/yvying-xixi/ops-monitor/agent-go/internal/reporter"
)

// fakeClient 记录回传结果。
type fakeClient struct {
	tasks    []reporter.PendingTask
	fetchErr error
	results  []reporter.TaskResult
}

func (f *fakeClient) FetchPendingTasks(context.Context) ([]reporter.PendingTask, error) {
	if f.fetchErr != nil {
		return nil, f.fetchErr
	}
	return f.tasks, nil
}

func (f *fakeClient) ReportTaskResult(_ context.Context, r reporter.TaskResult) error {
	f.results = append(f.results, r)
	return nil
}

// fakeExec 可编程执行器。
type fakeExec struct {
	actionOK   bool
	actionOut  string
	logsOK     bool
	logsOut    string
	actionErr  error
	lastAction string
}

func (f *fakeExec) RunAction(_ context.Context, _, action string, _ time.Duration) (bool, string) {
	f.lastAction = action
	return f.actionOK, f.actionOut
}

func (f *fakeExec) FetchLogs(context.Context, string, int) (bool, string) {
	return f.logsOK, f.logsOut
}

func TestPollOnceExecutesAndReports(t *testing.T) {
	client := &fakeClient{tasks: []reporter.PendingTask{
		{ExecutionID: 1, TaskID: 10, Action: "STATUS", ServiceName: "nginx", TimeoutSecond: 30},
	}}
	exec := &fakeExec{actionOK: true, actionOut: "active"}
	w := New(client, exec, time.Second, nil)

	n, err := w.PollOnce(context.Background())
	if err != nil {
		t.Fatalf("PollOnce 失败: %v", err)
	}
	if n != 1 {
		t.Fatalf("processed = %d, want 1", n)
	}
	if len(client.results) != 1 {
		t.Fatalf("回传数量 = %d", len(client.results))
	}
	r := client.results[0]
	if r.ExecutionID != 1 || r.Status != "SUCCESS" {
		t.Errorf("result = %+v", r)
	}
	if r.ResultText == nil || *r.ResultText != "active" {
		t.Errorf("result_text = %v", r.ResultText)
	}
}

func TestPollOnceLogsAction(t *testing.T) {
	client := &fakeClient{tasks: []reporter.PendingTask{
		{ExecutionID: 2, Action: "LOGS", ServiceName: "nginx", TimeoutSecond: 30},
	}}
	exec := &fakeExec{logsOK: true, logsOut: "log content"}
	w := New(client, exec, time.Second, nil)
	if _, err := w.PollOnce(context.Background()); err != nil {
		t.Fatalf("PollOnce 失败: %v", err)
	}
	if client.results[0].Status != "SUCCESS" {
		t.Errorf("status = %s", client.results[0].Status)
	}
	if client.results[0].Logs == nil || *client.results[0].Logs != "log content" {
		t.Errorf("logs = %v", client.results[0].Logs)
	}
}

func TestPollOnceReportsFailure(t *testing.T) {
	client := &fakeClient{tasks: []reporter.PendingTask{
		{ExecutionID: 3, Action: "START", ServiceName: "docker", TimeoutSecond: 30},
	}}
	exec := &fakeExec{actionOK: false, actionOut: "服务 docker 不在白名单内，拒绝执行"}
	w := New(client, exec, time.Second, nil)
	if _, err := w.PollOnce(context.Background()); err != nil {
		t.Fatalf("PollOnce 失败: %v", err)
	}
	r := client.results[0]
	if r.Status != "FAILED" {
		t.Errorf("status = %s", r.Status)
	}
	if r.ErrorMessage == nil || *r.ErrorMessage == "" {
		t.Errorf("error_message = %v", r.ErrorMessage)
	}
	if r.ErrorType == nil || *r.ErrorType != "SERVICE_NOT_WHITELISTED" {
		t.Errorf("error_type = %v", r.ErrorType)
	}
}

func TestPollOnceClassifiesTimeout(t *testing.T) {
	client := &fakeClient{tasks: []reporter.PendingTask{
		{ExecutionID: 4, Action: "RESTART", ServiceName: "nginx", TimeoutSecond: 5},
	}}
	exec := &fakeExec{actionOK: false, actionOut: "执行超时（5s）"}
	w := New(client, exec, time.Second, nil)
	if _, err := w.PollOnce(context.Background()); err != nil {
		t.Fatalf("PollOnce 失败: %v", err)
	}
	r := client.results[0]
	if r.ErrorType == nil || *r.ErrorType != "AGENT_EXECUTION_TIMEOUT" {
		t.Errorf("error_type = %v", r.ErrorType)
	}
}

func TestPollOnceEmpty(t *testing.T) {
	client := &fakeClient{tasks: nil}
	w := New(client, &fakeExec{}, time.Second, nil)
	n, err := w.PollOnce(context.Background())
	if err != nil {
		t.Fatalf("PollOnce 失败: %v", err)
	}
	if n != 0 {
		t.Errorf("processed = %d, want 0", n)
	}
}

func TestPollOnceFetchError(t *testing.T) {
	client := &fakeClient{fetchErr: errors.New("boom")}
	w := New(client, &fakeExec{}, time.Second, nil)
	if _, err := w.PollOnce(context.Background()); err == nil {
		t.Fatal("拉取失败应返回错误")
	}
}
