// Command agent 是 ops-monitor 的 Go 版 Linux Agent。
//
// 职责与 Python 版一致：注册、心跳、指标/资产/服务上报与受控任务执行，
// 通信协议见 docs/reference/agent-protocol.md。
package main

import (
	"context"
	"flag"
	"log/slog"
	"os"
	"os/signal"
	"sync"
	"syscall"
	"time"

	"github.com/yvying-xixi/ops-monitor/agent-go/internal/collector"
	"github.com/yvying-xixi/ops-monitor/agent-go/internal/config"
	"github.com/yvying-xixi/ops-monitor/agent-go/internal/executor"
	"github.com/yvying-xixi/ops-monitor/agent-go/internal/logger"
	"github.com/yvying-xixi/ops-monitor/agent-go/internal/reporter"
	"github.com/yvying-xixi/ops-monitor/agent-go/internal/signer"
	"github.com/yvying-xixi/ops-monitor/agent-go/internal/syscmd"
	"github.com/yvying-xixi/ops-monitor/agent-go/internal/worker"
)

// agentVersion 由构建注入（-ldflags "-X main.agentVersion=..."），默认与 Python 对齐。
var agentVersion = "1.0.0"

func main() {
	configPath := flag.String("config", "", "配置文件路径（默认 <可执行文件目录>/config/config.yaml）")
	showVersion := flag.Bool("version", false, "输出版本号并退出")
	flag.Parse()

	if *showVersion {
		os.Stdout.WriteString(agentVersion + "\n")
		return
	}

	cfg, err := config.Load(*configPath)
	if err != nil {
		os.Stderr.WriteString("加载配置失败: " + err.Error() + "\n")
		os.Exit(1)
	}

	log, closer, err := logger.Setup(cfg.Log.Level, cfg.Log.File)
	if err != nil {
		os.Stderr.WriteString("初始化日志失败: " + err.Error() + "\n")
		os.Exit(1)
	}
	if closer != nil {
		defer closer.Close()
	}
	slog.SetDefault(log)

	sig, err := signer.LoadOrCreate(cfg.Server.SigningKeyFile, cfg.Server.ServerCode)
	if err != nil {
		log.Error("初始化请求签名密钥失败", "err", err, "file", cfg.Server.SigningKeyFile)
		os.Exit(1)
	}
	log.Info("请求签名密钥已加载", "file", sig.KeyPath)

	client := reporter.NewClient(cfg.Server.URL, cfg.Server.Token, reporter.Options{
		Timeout:         time.Duration(cfg.Collect.RequestTimeout * float64(time.Second)),
		RetryMaxSeconds: cfg.Collect.RetryMaxSeconds,
		RetryMaxCount:   cfg.Collect.RetryMaxCount,
		Signer:          sig,
		Logger:          log,
	})

	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer stop()

	serverID, err := registerWithRetry(ctx, cfg, client, log)
	if err != nil {
		log.Error("注册未完成，进程退出", "err", err)
		os.Exit(1)
	}
	log.Info("Agent 已启动", "server_id", serverID, "version", agentVersion)

	var wg sync.WaitGroup
	start := func(name string, fn func()) {
		wg.Add(1)
		go func() {
			defer wg.Done()
			fn()
		}()
	}

	start("heartbeat", func() { heartbeatLoop(ctx, cfg, client, serverID, log) })
	start("metrics", func() { metricsLoop(ctx, cfg, client, serverID, log) })
	start("assets", func() { assetsLoop(ctx, cfg, client, serverID, log) })
	start("task-worker", func() { taskLoop(ctx, cfg, client, log) })

	<-ctx.Done()
	log.Info("Agent 正在停止...")
	wg.Wait()
	log.Info("Agent 已停止")
}

// registerWithRetry 注册并指数退避重试，直到成功或 ctx 取消。
func registerWithRetry(ctx context.Context, cfg *config.AgentConfig, client *reporter.Client, log *slog.Logger) (int64, error) {
	info := collector.CollectSystemInfo()
	delay := time.Second
	maxDelay := time.Duration(cfg.Collect.RetryMaxSeconds) * time.Second
	for {
		result, err := reporter.Register(ctx, client, cfg.Server.ServerCode, cfg.Server.Token, info, agentVersion)
		if err == nil {
			return result.ServerID, nil
		}
		log.Warn("注册失败，准备重试", "err", err, "delay", delay)
		select {
		case <-ctx.Done():
			return 0, ctx.Err()
		case <-time.After(delay):
		}
		delay *= 2
		if delay > maxDelay {
			delay = maxDelay
		}
	}
}

func heartbeatLoop(ctx context.Context, cfg *config.AgentConfig, client *reporter.Client, serverID int64, log *slog.Logger) {
	ticker := time.NewTicker(cfg.HeartbeatInterval())
	defer ticker.Stop()
	for {
		if err := reporter.SendHeartbeat(ctx, client, serverID, agentVersion); err != nil {
			log.Warn("心跳上报失败", "err", err)
		}
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
		}
	}
}

func metricsLoop(ctx context.Context, cfg *config.AgentConfig, client *reporter.Client, serverID int64, log *slog.Logger) {
	ticker := time.NewTicker(cfg.MetricsInterval())
	defer ticker.Stop()
	for {
		if err := reporter.SendMetrics(ctx, client, serverID, collector.CollectMetrics()); err != nil {
			log.Warn("指标上报失败", "err", err)
		}
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
		}
	}
}

func assetsLoop(ctx context.Context, cfg *config.AgentConfig, client *reporter.Client, serverID int64, log *slog.Logger) {
	services := collector.NewServiceCollector(syscmd.ExecRunner{})
	ticker := time.NewTicker(cfg.AssetsInterval())
	defer ticker.Stop()
	for {
		disks, networks := collector.CollectAssets()
		if err := reporter.SendAssets(ctx, client, serverID, disks, networks); err != nil {
			log.Warn("资产同步失败", "err", err)
		}
		statuses := services.Collect(cfg.Collect.Services)
		if err := reporter.SendServices(ctx, client, serverID, statuses); err != nil {
			log.Warn("服务状态同步失败", "err", err)
		}
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
		}
	}
}

func taskLoop(ctx context.Context, cfg *config.AgentConfig, client *reporter.Client, log *slog.Logger) {
	exec := executor.New(cfg.Collect.Services, syscmd.ExecRunner{})
	w := worker.New(worker.ReporterClient{Client: client}, exec, cfg.TaskPollInterval(), log)
	w.Run(ctx)
}
