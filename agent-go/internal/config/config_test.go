package config

import (
	"os"
	"path/filepath"
	"testing"
)

func writeConfig(t *testing.T, content string) string {
	t.Helper()
	dir := t.TempDir()
	path := filepath.Join(dir, "config.yaml")
	if err := os.WriteFile(path, []byte(content), 0o600); err != nil {
		t.Fatalf("写入配置失败: %v", err)
	}
	return path
}

func TestLoadFull(t *testing.T) {
	path := writeConfig(t, `
server:
  url: "http://127.0.0.1:8000"
  token: "test-token"
  server_code: "web-01"
collect:
  heartbeat_interval: 30
  metrics_interval: 10
log:
  level: "DEBUG"
`)
	cfg, err := Load(path)
	if err != nil {
		t.Fatalf("Load 失败: %v", err)
	}
	if cfg.Server.URL != "http://127.0.0.1:8000" {
		t.Errorf("url = %q", cfg.Server.URL)
	}
	if cfg.Server.Token != "test-token" {
		t.Errorf("token = %q", cfg.Server.Token)
	}
	if cfg.Server.ServerCode != "web-01" {
		t.Errorf("server_code = %q", cfg.Server.ServerCode)
	}
	if cfg.Collect.HeartbeatInterval != 30 || cfg.Collect.MetricsInterval != 10 {
		t.Errorf("interval 值不符: %+v", cfg.Collect)
	}
	if cfg.Log.Level != "DEBUG" {
		t.Errorf("level = %q", cfg.Log.Level)
	}
	// 未指定字段使用默认值
	if cfg.Collect.AssetsInterval != 60 {
		t.Errorf("assets_interval = %d, want 60", cfg.Collect.AssetsInterval)
	}
	if cfg.Collect.RetryMaxSeconds != 60 {
		t.Errorf("retry_max_seconds = %d, want 60", cfg.Collect.RetryMaxSeconds)
	}
	if len(cfg.Collect.Services) != 3 {
		t.Errorf("services = %v, want 默认三项", cfg.Collect.Services)
	}
}

func TestLoadRequiresToken(t *testing.T) {
	path := writeConfig(t, `
server:
  url: "http://127.0.0.1:8000"
  token: ""
  server_code: "web-01"
`)
	if _, err := Load(path); err == nil {
		t.Fatal("token 为空时应报错")
	}
}

func TestLoadRequiresServerCode(t *testing.T) {
	path := writeConfig(t, `
server:
  url: "http://127.0.0.1:8000"
  token: "t"
  server_code: ""
`)
	if _, err := Load(path); err == nil {
		t.Fatal("server_code 为空时应报错")
	}
}

func TestLoadRejectsOutOfRangeInterval(t *testing.T) {
	path := writeConfig(t, `
server:
  url: "http://127.0.0.1:8000"
  token: "t"
  server_code: "web-01"
collect:
  heartbeat_interval: 1
`)
	if _, err := Load(path); err == nil {
		t.Fatal("heartbeat_interval < 5 时应报错")
	}
}

func TestLoadMissingFile(t *testing.T) {
	if _, err := Load(filepath.Join(t.TempDir(), "none.yaml")); err == nil {
		t.Fatal("文件不存在时应报错")
	}
}
