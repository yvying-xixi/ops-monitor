// Package reporter 封装与 Backend 的 HTTP 通信：Bearer 鉴权、指数退避重试与各上报接口。
package reporter

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log/slog"
	"math/rand"
	"net"
	"net/http"
	"net/url"
	"time"

	"github.com/yvying-xixi/ops-monitor/agent-go/internal/signer"
)

const (
	// MaxIdleRetries 单次请求最多退避重试次数上限，避免无限循环。
	maxRetryDelay = 60 * time.Second
)

// ReporterError 上报异常。
type ReporterError struct {
	msg string
}

func (e *ReporterError) Error() string { return e.msg }

// Client Agent 上报 HTTP 客户端。
type Client struct {
	baseURL         string
	token           string
	httpClient      *http.Client
	retryMaxSeconds int
	retryMaxCount   int
	signer          *signer.Signer
	logger          *slog.Logger
}

// Options 客户端可选配置。
type Options struct {
	Timeout         time.Duration
	RetryMaxSeconds int
	RetryMaxCount   int
	Signer          *signer.Signer
	HTTPClient      *http.Client
	Logger          *slog.Logger
}

// NewClient 创建上报客户端。
func NewClient(baseURL, token string, opts Options) *Client {
	if opts.Timeout <= 0 {
		opts.Timeout = 10 * time.Second
	}
	if opts.RetryMaxSeconds <= 0 {
		opts.RetryMaxSeconds = 60
	}
	if opts.RetryMaxCount <= 0 {
		opts.RetryMaxCount = 2
	}
	if opts.Logger == nil {
		opts.Logger = slog.Default()
	}
	httpClient := opts.HTTPClient
	if httpClient == nil {
		httpClient = &http.Client{
			Timeout: opts.Timeout,
			Transport: &http.Transport{
				DialContext: (&net.Dialer{Timeout: opts.Timeout}).DialContext,
			},
		}
	}
	return &Client{
		baseURL:         baseURL,
		token:           token,
		httpClient:      httpClient,
		retryMaxSeconds: opts.RetryMaxSeconds,
		retryMaxCount:   opts.RetryMaxCount,
		signer:          opts.Signer,
		logger:          opts.Logger,
	}
}

// SigningPublicKey 返回 base64 Ed25519 公钥；未配置签名时返回空串。
func (c *Client) SigningPublicKey() string {
	if c.signer == nil {
		return ""
	}
	return c.signer.PublicKeyB64()
}

// envelope 后端统一响应结构 {code, message, data}。
type envelope struct {
	Code    int             `json:"code"`
	Message string          `json:"message"`
	Data    json.RawMessage `json:"data"`
}

// request 执行一次请求并按指数退避重试网络错误，返回 data 字段。
func (c *Client) request(ctx context.Context, method, path string, body any) (json.RawMessage, error) {
	var payload []byte
	if body != nil {
		var err error
		payload, err = json.Marshal(body)
		if err != nil {
			return nil, &ReporterError{msg: fmt.Sprintf("序列化请求体失败: %v", err)}
		}
	}

	var headers map[string]string
	if c.signer != nil {
		headers = c.signer.SignHeaders(method, path, payload)
	}

	delay := time.Second
	maxDelay := time.Duration(c.retryMaxSeconds) * time.Second
	if maxDelay > maxRetryDelay {
		maxDelay = maxRetryDelay
	}
	attempt := 0
	for {
		raw, retryable, err := c.doOnce(ctx, method, path, payload, headers)
		if err == nil {
			c.logger.Info("上报成功", "method", method, "path", path)
			return raw, nil
		}
		if !retryable {
			return nil, err
		}
		attempt++
		if attempt > c.retryMaxCount {
			return nil, &ReporterError{msg: fmt.Sprintf("请求 %s 超过最大重试次数: %v", path, err)}
		}
		if delay >= maxDelay {
			return nil, &ReporterError{msg: fmt.Sprintf("请求 %s 最终失败: %v", path, err)}
		}
		// 加入 0~50% 随机抖动，降低集中重试冲击
		sleep := delay + time.Duration(rand.Int63n(int64(delay/2)+1))
		if sleep > maxDelay {
			sleep = maxDelay
		}
		c.logger.Warn("请求失败，准备重试", "path", path, "err", err, "delay", sleep, "attempt", attempt)
		select {
		case <-ctx.Done():
			return nil, &ReporterError{msg: fmt.Sprintf("请求 %s 被取消: %v", path, ctx.Err())}
		case <-time.After(sleep):
		}
		delay *= 2
		if delay > maxDelay {
			delay = maxDelay
		}
	}
}

// doOnce 执行单次请求。返回 (data, 是否可重试, error)。
func (c *Client) doOnce(ctx context.Context, method, path string, payload []byte, headers map[string]string) (json.RawMessage, bool, error) {
	fullURL, err := url.JoinPath(c.baseURL, path)
	if err != nil {
		return nil, false, &ReporterError{msg: fmt.Sprintf("拼接 URL 失败: %v", err)}
	}
	var reader io.Reader
	if payload != nil {
		reader = bytes.NewReader(payload)
	}
	req, err := http.NewRequestWithContext(ctx, method, fullURL, reader)
	if err != nil {
		return nil, false, &ReporterError{msg: fmt.Sprintf("构造请求失败: %v", err)}
	}
	req.Header.Set("Authorization", "Bearer "+c.token)
	for key, value := range headers {
		req.Header.Set(key, value)
	}
	if payload != nil && req.Header.Get("Content-Type") == "" {
		req.Header.Set("Content-Type", "application/json")
	}

	resp, err := c.httpClient.Do(req)
	if err != nil {
		// 传输层错误：可重试
		return nil, true, err
	}
	defer resp.Body.Close()

	raw, readErr := io.ReadAll(resp.Body)
	if readErr != nil {
		return nil, true, readErr
	}
	var env envelope
	if len(raw) > 0 {
		if jsonErr := json.Unmarshal(raw, &env); jsonErr != nil {
			return nil, false, &ReporterError{msg: fmt.Sprintf("%s 响应解析失败", path)}
		}
	}
	if resp.StatusCode >= 400 {
		message := env.Message
		if message == "" {
			message = "unknown error"
		}
		return nil, false, &ReporterError{msg: fmt.Sprintf("%s 返回 %d: %s", path, resp.StatusCode, message)}
	}
	if len(env.Data) == 0 || string(env.Data) == "null" {
		return json.RawMessage("{}"), false, nil
	}
	return env.Data, false, nil
}

// Post 发送 POST 请求并返回 data。
func (c *Client) Post(ctx context.Context, path string, body any) (json.RawMessage, error) {
	return c.request(ctx, http.MethodPost, path, body)
}

// Get 发送 GET 请求并返回 data。
func (c *Client) Get(ctx context.Context, path string) (json.RawMessage, error) {
	return c.request(ctx, http.MethodGet, path, nil)
}
