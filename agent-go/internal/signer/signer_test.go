package signer

import (
	"crypto/ed25519"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"path/filepath"
	"testing"
)

func TestLoadOrCreatePersistsKey(t *testing.T) {
	keyFile := filepath.Join(t.TempDir(), "agent_ed25519.key")
	first, err := LoadOrCreate(keyFile, "web-01")
	if err != nil {
		t.Fatalf("LoadOrCreate 失败: %v", err)
	}
	second, err := LoadOrCreate(keyFile, "web-01")
	if err != nil {
		t.Fatalf("LoadOrCreate 失败: %v", err)
	}
	if first.PublicKeyB64() != second.PublicKeyB64() {
		t.Fatal("重新加载后公钥不一致")
	}
}

func TestSignHeadersVerifiable(t *testing.T) {
	keyFile := filepath.Join(t.TempDir(), "agent_ed25519.key")
	s, err := LoadOrCreate(keyFile, "web-01")
	if err != nil {
		t.Fatalf("LoadOrCreate 失败: %v", err)
	}
	body := []byte(`{"a":1}`)
	headers := s.SignHeaders("POST", "/api/v1/agent/heartbeat", body)

	if headers["X-Agent-Id"] != "web-01" {
		t.Fatalf("X-Agent-Id = %s", headers["X-Agent-Id"])
	}
	sum := sha256.Sum256(body)
	canonical := "POST\n/api/v1/agent/heartbeat\n" + headers["X-Timestamp"] + "\n" +
		headers["X-Request-Id"] + "\n" + hex.EncodeToString(sum[:])

	pubBytes, err := base64.StdEncoding.DecodeString(s.PublicKeyB64())
	if err != nil {
		t.Fatalf("公钥解码失败: %v", err)
	}
	sig, err := base64.StdEncoding.DecodeString(headers["X-Signature"])
	if err != nil {
		t.Fatalf("签名解码失败: %v", err)
	}
	if !ed25519.Verify(ed25519.PublicKey(pubBytes), []byte(canonical), sig) {
		t.Fatal("签名验证失败")
	}
}
