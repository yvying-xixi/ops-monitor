// Package signer 提供 Ed25519 请求签名（见 ADR-010）。
package signer

import (
	"crypto/ed25519"
	"crypto/rand"
	"crypto/sha256"
	"crypto/x509"
	"encoding/base64"
	"encoding/hex"
	"encoding/pem"
	"fmt"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"time"
)

// Signer 持有 Ed25519 私钥，为 Agent 请求生成签名头。
type Signer struct {
	priv       ed25519.PrivateKey
	serverCode string
	KeyPath    string
}

// LoadOrCreate 加载私钥；不存在则生成并以 0600 权限落盘。
func LoadOrCreate(keyFile, serverCode string) (*Signer, error) {
	if data, err := os.ReadFile(keyFile); err == nil {
		block, _ := pem.Decode(data)
		if block == nil {
			return nil, fmt.Errorf("私钥 PEM 解析失败: %s", keyFile)
		}
		key, err := x509.ParsePKCS8PrivateKey(block.Bytes)
		if err != nil {
			return nil, fmt.Errorf("私钥解析失败: %w", err)
		}
		edKey, ok := key.(ed25519.PrivateKey)
		if !ok {
			return nil, fmt.Errorf("私钥类型不匹配: %s", keyFile)
		}
		return &Signer{priv: edKey, serverCode: serverCode, KeyPath: keyFile}, nil
	}

	_, priv, err := ed25519.GenerateKey(rand.Reader)
	if err != nil {
		return nil, err
	}
	der, err := x509.MarshalPKCS8PrivateKey(priv)
	if err != nil {
		return nil, err
	}
	if err := os.MkdirAll(filepath.Dir(keyFile), 0o700); err != nil {
		return nil, err
	}
	pemData := pem.EncodeToMemory(&pem.Block{Type: "PRIVATE KEY", Bytes: der})
	if err := os.WriteFile(keyFile, pemData, 0o600); err != nil {
		return nil, err
	}
	return &Signer{priv: priv, serverCode: serverCode, KeyPath: keyFile}, nil
}

// PublicKeyB64 返回 base64 编码的 Ed25519 公钥。
func (s *Signer) PublicKeyB64() string {
	pub := s.priv.Public().(ed25519.PublicKey)
	return base64.StdEncoding.EncodeToString(pub)
}

// SignHeaders 构造签名请求头。
func (s *Signer) SignHeaders(method, path string, body []byte) map[string]string {
	timestamp := strconv.FormatInt(time.Now().Unix(), 10)
	requestID := randomHex(16)
	canonical := strings.Join(
		[]string{strings.ToUpper(method), path, timestamp, requestID, sha256Hex(body)},
		"\n",
	)
	signature := ed25519.Sign(s.priv, []byte(canonical))
	return map[string]string{
		"X-Agent-Id":   s.serverCode,
		"X-Timestamp":  timestamp,
		"X-Request-Id": requestID,
		"X-Signature":  base64.StdEncoding.EncodeToString(signature),
	}
}

func sha256Hex(body []byte) string {
	sum := sha256.Sum256(body)
	return hex.EncodeToString(sum[:])
}

func randomHex(n int) string {
	buf := make([]byte, n)
	_, _ = rand.Read(buf)
	return hex.EncodeToString(buf)
}
