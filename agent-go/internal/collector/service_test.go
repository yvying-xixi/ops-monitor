package collector

import (
	"context"
	"errors"
	"testing"
	"time"

	"github.com/yvying-xixi/ops-monitor/agent-go/internal/syscmd"
)

// fakeRunner 可编程的 Runner。
type fakeRunner struct {
	results map[string]syscmd.Result
	errs    map[string]error
}

func (f fakeRunner) Run(_ context.Context, _ time.Duration, name string, args ...string) (syscmd.Result, error) {
	key := name
	for _, a := range args {
		key += " " + a
	}
	if err, ok := f.errs[key]; ok {
		return syscmd.Result{}, err
	}
	if res, ok := f.results[key]; ok {
		return res, nil
	}
	return syscmd.Result{ExitCode: 1}, nil
}

func TestServiceCollectorMapping(t *testing.T) {
	runner := fakeRunner{results: map[string]syscmd.Result{
		"systemctl is-active nginx":  {Stdout: "active\n", ExitCode: 0},
		"systemctl is-active docker": {Stdout: "inactive\n", ExitCode: 3},
		"systemctl is-active redis":  {Stdout: "failed\n", ExitCode: 1},
		"systemctl is-active weird":  {Stdout: "reloading\n", ExitCode: 1},
	}}
	c := NewServiceCollector(runner)
	got := c.Collect([]string{"nginx", "docker", "redis", "weird"})
	want := []string{StatusRunning, StatusStopped, StatusFailed, StatusUnknown}
	if len(got) != len(want) {
		t.Fatalf("数量不符: %d", len(got))
	}
	for i, s := range got {
		if s.CurrentStatus != want[i] {
			t.Errorf("%s = %s, want %s", s.ServiceName, s.CurrentStatus, want[i])
		}
	}
}

func TestServiceCollectorSubprocessErrorUnknown(t *testing.T) {
	runner := fakeRunner{errs: map[string]error{
		"systemctl is-active nginx": errors.New("no systemctl"),
	}}
	c := NewServiceCollector(runner)
	got := c.Collect([]string{"nginx"})
	if got[0].CurrentStatus != StatusUnknown {
		t.Errorf("status = %s, want UNKNOWN", got[0].CurrentStatus)
	}
}
