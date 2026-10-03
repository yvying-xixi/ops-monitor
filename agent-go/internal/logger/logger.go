// Package logger 构建 Agent 的结构化日志器。
package logger

import (
	"io"
	"log/slog"
	"os"
	"strings"
)

// Setup 创建日志器：level 支持 DEBUG/INFO/WARN/ERROR；file 为空时输出到标准输出。
func Setup(level, file string) (*slog.Logger, io.Closer, error) {
	var out io.Writer = os.Stdout
	var closer io.Closer
	if strings.TrimSpace(file) != "" {
		f, err := os.OpenFile(file, os.O_CREATE|os.O_APPEND|os.O_WRONLY, 0o640)
		if err != nil {
			return nil, nil, err
		}
		out = f
		closer = f
	}
	handler := slog.NewTextHandler(out, &slog.HandlerOptions{Level: parseLevel(level)})
	return slog.New(handler).With("component", "agent"), closer, nil
}

// parseLevel 将字符串级别映射为 slog.Level。
func parseLevel(level string) slog.Level {
	switch strings.ToUpper(strings.TrimSpace(level)) {
	case "DEBUG":
		return slog.LevelDebug
	case "WARN", "WARNING":
		return slog.LevelWarn
	case "ERROR":
		return slog.LevelError
	default:
		return slog.LevelInfo
	}
}
