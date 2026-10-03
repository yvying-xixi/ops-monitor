package reporter

import (
	"context"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"sync/atomic"
	"testing"
	"time"

	"github.com/yvying-xixi/ops-monitor/agent-go/internal/collector"
)

func newTestClient(t *testing.T, handler http.HandlerFunc, retrySeconds int) (*Client, *httptest.Server) {
	t.Helper()
	srv := httptest.NewServer(handler)
	t.Cleanup(srv.Close)
	c := NewClient(srv.URL, "secret-token", Options{
		Timeout:         2 * time.Second,
		RetryMaxSeconds: retrySeconds,
	})
	return c, srv
}

func successEnvelope(data any) []byte {
	b, _ := json.Marshal(map[string]any{"code": 0, "message": "ok", "data": data})
	return b
}

func TestClientInjectsBearerHeader(t *testing.T) {
	var gotAuth string
	c, _ := newTestClient(t, func(w http.ResponseWriter, r *http.Request) {
		gotAuth = r.Header.Get("Authorization")
		w.Write(successEnvelope(map[string]any{"ok": true}))
	}, 4)
	if _, err := c.Post(context.Background(), "/api/v1/agent/heartbeat", map[string]any{}); err != nil {
		t.Fatalf("Post 失败: %v", err)
	}
	if gotAuth != "Bearer secret-token" {
		t.Errorf("Authorization = %q", gotAuth)
	}
}

func TestSendMetricsPayload(t *testing.T) {
	var captured map[string]any
	c, _ := newTestClient(t, func(w http.ResponseWriter, r *http.Request) {
		body, _ := io.ReadAll(r.Body)
		_ = json.Unmarshal(body, &captured)
		w.Write(successEnvelope(map[string]any{"server_id": 1}))
	}, 4)
	err := SendMetrics(context.Background(), c, 1, collector.Metrics{CPUUsage: 50, Load1m: 1, Load5m: 2, Load15m: 3, TCPConnections: 7, UptimeSeconds: 10})
	if err != nil {
		t.Fatalf("SendMetrics 失败: %v", err)
	}
	if captured["server_id"].(float64) != 1 {
		t.Errorf("server_id = %v", captured["server_id"])
	}
	if captured["cpu_usage"].(float64) != 50 {
		t.Errorf("cpu_usage = %v", captured["cpu_usage"])
	}
	if _, ok := captured["timestamp"]; !ok {
		t.Error("缺少 timestamp")
	}
}

func TestSendHeartbeatPayload(t *testing.T) {
	var captured map[string]any
	c, _ := newTestClient(t, func(w http.ResponseWriter, r *http.Request) {
		body, _ := io.ReadAll(r.Body)
		_ = json.Unmarshal(body, &captured)
		w.Write(successEnvelope(map[string]any{}))
	}, 4)
	if err := SendHeartbeat(context.Background(), c, 1, "1.0.0"); err != nil {
		t.Fatalf("SendHeartbeat 失败: %v", err)
	}
	if captured["agent_version"] != "1.0.0" {
		t.Errorf("agent_version = %v", captured["agent_version"])
	}
}

func TestRegisterPayload(t *testing.T) {
	var captured map[string]any
	c, _ := newTestClient(t, func(w http.ResponseWriter, r *http.Request) {
		body, _ := io.ReadAll(r.Body)
		_ = json.Unmarshal(body, &captured)
		w.Write(successEnvelope(map[string]any{"server_id": 7, "agent_status": "ONLINE"}))
	}, 4)
	info := collector.SystemInfo{Hostname: "web-01", CPUCores: 4}
	res, err := Register(context.Background(), c, "web-01", "secret-token", info, "1.0.0")
	if err != nil {
		t.Fatalf("Register 失败: %v", err)
	}
	if res.ServerID != 7 {
		t.Errorf("server_id = %d", res.ServerID)
	}
	if captured["server_code"] != "web-01" || captured["token"] != "secret-token" {
		t.Errorf("payload 不符: %v", captured)
	}
	if captured["cpu_cores"].(float64) != 4 {
		t.Errorf("cpu_cores = %v", captured["cpu_cores"])
	}
}

func TestRetryThenSuccess(t *testing.T) {
	var count int32
	c, _ := newTestClient(t, func(w http.ResponseWriter, r *http.Request) {
		if atomic.AddInt32(&count, 1) == 1 {
			// 关闭连接制造传输错误
			hj, _ := w.(http.Hijacker)
			conn, _, _ := hj.Hijack()
			conn.Close()
			return
		}
		w.Write(successEnvelope(map[string]any{"retried": true}))
	}, 4)
	if _, err := c.Post(context.Background(), "/api/v1/agent/heartbeat", map[string]any{}); err != nil {
		t.Fatalf("重试后应成功: %v", err)
	}
	if atomic.LoadInt32(&count) < 2 {
		t.Errorf("count = %d, want >= 2", count)
	}
}

func TestHTTPErrorStatusRaises(t *testing.T) {
	c, _ := newTestClient(t, func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusUnauthorized)
		b, _ := json.Marshal(map[string]any{"code": 40103, "message": "Agent 凭证无效"})
		w.Write(b)
	}, 4)
	if _, err := c.Post(context.Background(), "/api/v1/agent/heartbeat", map[string]any{}); err == nil {
		t.Fatal("401 应返回错误")
	}
}

func TestRetryExhaustedRaises(t *testing.T) {
	c, _ := newTestClient(t, func(w http.ResponseWriter, r *http.Request) {
		hj, _ := w.(http.Hijacker)
		conn, _, _ := hj.Hijack()
		conn.Close()
	}, 1)
	start := time.Now()
	if _, err := c.Post(context.Background(), "/api/v1/agent/heartbeat", map[string]any{}); err == nil {
		t.Fatal("重试耗尽应返回错误")
	}
	if time.Since(start) > 10*time.Second {
		t.Error("重试耗时过长，可能未按封顶退避")
	}
}
