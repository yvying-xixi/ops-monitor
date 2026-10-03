package executor

import (
	"context"
	"errors"
	"strings"
	"testing"
	"time"

	"github.com/yvying-xixi/ops-monitor/agent-go/internal/syscmd"
)

// spyRunner 记录调用参数，便于断言命令列表与超时。
type spyRunner struct {
	calls   [][]string
	timeout time.Duration
	result  syscmd.Result
	err     error
}

func (s *spyRunner) Run(_ context.Context, timeout time.Duration, name string, args ...string) (syscmd.Result, error) {
	s.timeout = timeout
	call := append([]string{name}, args...)
	s.calls = append(s.calls, call)
	return s.result, s.err
}

func TestValidateWhitelist(t *testing.T) {
	e := New([]string{"nginx"}, &spyRunner{})
	if err := e.Validate("apache2", "START"); err == nil {
		t.Fatal("非白名单服务应被拒绝")
	}
}

func TestValidateAction(t *testing.T) {
	e := New([]string{"nginx"}, &spyRunner{})
	if err := e.Validate("nginx", "SHELL"); err == nil {
		t.Fatal("非法操作应被拒绝")
	}
}

func TestRunActionSuccess(t *testing.T) {
	r := &spyRunner{result: syscmd.Result{Stdout: "active", ExitCode: 0}}
	e := New([]string{"nginx"}, r)
	ok, out := e.RunAction(context.Background(), "nginx", "STATUS", 0)
	if !ok || out != "active" {
		t.Errorf("ok=%v out=%q", ok, out)
	}
}

func TestRunActionFailure(t *testing.T) {
	r := &spyRunner{result: syscmd.Result{Stderr: "Job failed", ExitCode: 1}}
	e := New([]string{"nginx"}, r)
	ok, out := e.RunAction(context.Background(), "nginx", "START", 0)
	if ok {
		t.Error("非零退出码应视为失败")
	}
	if !strings.Contains(strings.ToLower(out), "failed") {
		t.Errorf("out = %q", out)
	}
}

func TestRunActionTimeout(t *testing.T) {
	r := &spyRunner{err: context.DeadlineExceeded}
	e := New([]string{"nginx"}, r)
	ok, out := e.RunAction(context.Background(), "nginx", "RESTART", 5*time.Second)
	if ok {
		t.Error("超时应失败")
	}
	if !strings.Contains(out, "超时") {
		t.Errorf("out = %q", out)
	}
}

func TestNoShellInvocation(t *testing.T) {
	r := &spyRunner{result: syscmd.Result{ExitCode: 0}}
	e := New([]string{"nginx"}, r)
	e.RunAction(context.Background(), "nginx", "RESTART", 0)
	if len(r.calls) != 1 {
		t.Fatalf("调用次数 = %d", len(r.calls))
	}
	want := []string{"systemctl", "restart", "nginx"}
	got := r.calls[0]
	if len(got) != len(want) {
		t.Fatalf("参数 = %v, want %v", got, want)
	}
	for i := range want {
		if got[i] != want[i] {
			t.Errorf("参数[%d] = %q, want %q", i, got[i], want[i])
		}
	}
}

func TestRunActionDefaultTimeout(t *testing.T) {
	r := &spyRunner{result: syscmd.Result{ExitCode: 0}}
	e := New([]string{"nginx"}, r)
	e.RunAction(context.Background(), "nginx", "START", 0)
	if r.timeout != 60*time.Second {
		t.Errorf("默认超时 = %v, want 60s", r.timeout)
	}
}

func TestFetchLogs(t *testing.T) {
	r := &spyRunner{result: syscmd.Result{Stdout: "log line 1\nlog line 2", ExitCode: 0}}
	e := New([]string{"nginx"}, r)
	ok, out := e.FetchLogs(context.Background(), "nginx", 10)
	if !ok {
		t.Fatal("抓取日志应成功")
	}
	if !strings.Contains(out, "log line 1") {
		t.Errorf("out = %q", out)
	}
	want := []string{"journalctl", "-n", "10", "-u", "nginx", "--no-pager"}
	for i := range want {
		if r.calls[0][i] != want[i] {
			t.Errorf("参数[%d] = %q, want %q", i, r.calls[0][i], want[i])
		}
	}
}

func TestFetchLogsWhitelist(t *testing.T) {
	e := New([]string{"nginx"}, &spyRunner{})
	ok, _ := e.FetchLogs(context.Background(), "docker", 0)
	if ok {
		t.Error("非白名单服务日志应拒绝")
	}
}

var _ = errors.New
