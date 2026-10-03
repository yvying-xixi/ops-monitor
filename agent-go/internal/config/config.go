// Package config 负责加载与校验 Agent 的 config.yaml。
//
// 配置 schema 与 Python 版 Agent 完全一致，两者可复用同一份配置文件。
package config

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"time"

	"gopkg.in/yaml.v3"
)

// ServerConfig 服务端连接配置。
type ServerConfig struct {
	URL            string `yaml:"url"`
	Token          string `yaml:"token"`
	ServerCode     string `yaml:"server_code"`
	SigningKeyFile string `yaml:"signing_key_file"`
}

// CollectConfig 采集与上报周期配置。
type CollectConfig struct {
	HeartbeatInterval int      `yaml:"heartbeat_interval"`
	MetricsInterval   int      `yaml:"metrics_interval"`
	AssetsInterval    int      `yaml:"assets_interval"`
	TaskPollInterval  int      `yaml:"task_poll_interval"`
	RetryMaxSeconds   int      `yaml:"retry_max_seconds"`
	RetryMaxCount     int      `yaml:"retry_max_count"`
	ConnectTimeout    float64  `yaml:"connect_timeout"`
	RequestTimeout    float64  `yaml:"request_timeout"`
	Services          []string `yaml:"services"`
}

// LogConfig 日志配置。
type LogConfig struct {
	Level string `yaml:"level"`
	File  string `yaml:"file"`
}

// AgentConfig Agent 总配置。
type AgentConfig struct {
	Server  ServerConfig  `yaml:"server"`
	Collect CollectConfig `yaml:"collect"`
	Log     LogConfig     `yaml:"log"`
}

// Default 返回内置默认值，用于在加载时补齐缺失字段。
func defaults() AgentConfig {
	return AgentConfig{
		Server: ServerConfig{SigningKeyFile: "agent_ed25519.key"},
		Collect: CollectConfig{
			HeartbeatInterval: 30,
			MetricsInterval:   10,
			AssetsInterval:    60,
			TaskPollInterval:  5,
			RetryMaxSeconds:   60,
			RetryMaxCount:     2,
			ConnectTimeout:    5,
			RequestTimeout:    10,
			Services:          []string{"nginx", "docker", "ssh"},
		},
		Log: LogConfig{Level: "INFO"},
	}
}

// applyDefaults 将零值字段替换为默认值（与 pydantic 默认语义对齐）。
func applyDefaults(c *AgentConfig) {
	d := defaults()
	if c.Collect.HeartbeatInterval == 0 {
		c.Collect.HeartbeatInterval = d.Collect.HeartbeatInterval
	}
	if c.Collect.MetricsInterval == 0 {
		c.Collect.MetricsInterval = d.Collect.MetricsInterval
	}
	if c.Collect.AssetsInterval == 0 {
		c.Collect.AssetsInterval = d.Collect.AssetsInterval
	}
	if c.Collect.TaskPollInterval == 0 {
		c.Collect.TaskPollInterval = d.Collect.TaskPollInterval
	}
	if c.Collect.RetryMaxSeconds == 0 {
		c.Collect.RetryMaxSeconds = d.Collect.RetryMaxSeconds
	}
	if c.Collect.RetryMaxCount == 0 {
		c.Collect.RetryMaxCount = d.Collect.RetryMaxCount
	}
	if c.Collect.ConnectTimeout == 0 {
		c.Collect.ConnectTimeout = d.Collect.ConnectTimeout
	}
	if c.Collect.RequestTimeout == 0 {
		c.Collect.RequestTimeout = d.Collect.RequestTimeout
	}
	if c.Server.SigningKeyFile == "" {
		c.Server.SigningKeyFile = d.Server.SigningKeyFile
	}
	if len(c.Collect.Services) == 0 {
		c.Collect.Services = d.Collect.Services
	}
	if c.Log.Level == "" {
		c.Log.Level = d.Log.Level
	}
}

// validate 校验必填项与范围（对齐 Python 版 pydantic 约束）。
func validate(c *AgentConfig) error {
	if strings.TrimSpace(c.Server.URL) == "" {
		return fmt.Errorf("server.url 不能为空")
	}
	if strings.TrimSpace(c.Server.Token) == "" {
		return fmt.Errorf("server.token 不能为空")
	}
	if strings.TrimSpace(c.Server.ServerCode) == "" {
		return fmt.Errorf("server.server_code 不能为空")
	}
	if c.Collect.HeartbeatInterval < 5 {
		return fmt.Errorf("collect.heartbeat_interval 需 >= 5")
	}
	if c.Collect.MetricsInterval < 2 {
		return fmt.Errorf("collect.metrics_interval 需 >= 2")
	}
	if c.Collect.AssetsInterval < 10 {
		return fmt.Errorf("collect.assets_interval 需 >= 10")
	}
	if c.Collect.TaskPollInterval < 2 {
		return fmt.Errorf("collect.task_poll_interval 需 >= 2")
	}
	if c.Collect.RetryMaxSeconds < 1 {
		return fmt.Errorf("collect.retry_max_seconds 需 >= 1")
	}
	if c.Collect.RetryMaxCount < 1 {
		return fmt.Errorf("collect.retry_max_count 需 >= 1")
	}
	if c.Collect.ConnectTimeout <= 0 {
		return fmt.Errorf("collect.connect_timeout 需 > 0")
	}
	if c.Collect.RequestTimeout <= 0 {
		return fmt.Errorf("collect.request_timeout 需 > 0")
	}
	return nil
}

// Load 从指定路径加载配置；path 为空时使用可执行文件同级的 config/config.yaml。
func Load(path string) (*AgentConfig, error) {
	if path == "" {
		path = DefaultPath()
	}
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("读取配置失败 %s: %w", path, err)
	}
	cfg := defaults()
	if err := yaml.Unmarshal(raw, &cfg); err != nil {
		return nil, fmt.Errorf("解析配置失败 %s: %w", path, err)
	}
	applyDefaults(&cfg)
	// 私钥路径相对配置文件目录解析，避免受运行目录影响
	if !filepath.IsAbs(cfg.Server.SigningKeyFile) {
		cfg.Server.SigningKeyFile = filepath.Join(filepath.Dir(path), cfg.Server.SigningKeyFile)
	}
	if err := validate(&cfg); err != nil {
		return nil, err
	}
	return &cfg, nil
}

// DefaultPath 返回默认配置文件路径（相对可执行文件）。
func DefaultPath() string {
	exe, err := os.Executable()
	if err != nil {
		return filepath.Join("config", "config.yaml")
	}
	return filepath.Join(filepath.Dir(exe), "config", "config.yaml")
}

// HeartbeatInterval 返回心跳周期。
func (c *AgentConfig) HeartbeatInterval() time.Duration {
	return time.Duration(c.Collect.HeartbeatInterval) * time.Second
}

// MetricsInterval 返回指标采集周期。
func (c *AgentConfig) MetricsInterval() time.Duration {
	return time.Duration(c.Collect.MetricsInterval) * time.Second
}

// AssetsInterval 返回资产同步周期。
func (c *AgentConfig) AssetsInterval() time.Duration {
	return time.Duration(c.Collect.AssetsInterval) * time.Second
}

// TaskPollInterval 返回任务轮询周期。
func (c *AgentConfig) TaskPollInterval() time.Duration {
	return time.Duration(c.Collect.TaskPollInterval) * time.Second
}
