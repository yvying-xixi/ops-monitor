#!/usr/bin/env python3
"""解析 deploy/config.yml，校验配置并渲染 deploy/.env。

用法：
    python3 prepare.py [config.yml] [.env]        # 校验 + 渲染 + 回写生成的密钥
    python3 prepare.py --check [config.yml]       # 仅校验，不写任何文件

约定：
    - config.yml 是唯一配置源；.env 为渲染产物
    - 空密码/密钥自动生成并**按 section 定向回写** config.yml（保留注释）
"""

from __future__ import annotations

import argparse
import os
import re
import secrets
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    print("缺少 PyYAML，请执行：apt install -y python3-yaml 或 pip install pyyaml", file=sys.stderr)
    sys.exit(2)

WEAK_PASSWORDS = {"", "change-me", "changeme", "password", "123456", "admin", "admin123456"}
MIN_SECRET_LEN = 8


def gen_secret() -> str:
    return secrets.token_urlsafe(24)


def load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def set_yaml_scalar(text: str, section: str, key: str, value: str) -> str:
    """按 section 定向替换标量值，保留注释与其他内容。"""
    lines = text.splitlines()
    out: list[str] = []
    in_section = False
    for line in lines:
        if re.match(rf"^{re.escape(section)}:\s*$", line):
            in_section = True
            out.append(line)
            continue
        if in_section and re.match(r"^\S", line):  # 遇到下一个顶层键
            in_section = False
        if in_section and re.match(rf"^\s+{re.escape(key)}:\s", line):
            indent = line[: len(line) - len(line.lstrip())]
            out.append(f'{indent}{key}: "{value}"')
            continue
        out.append(line)
    return "\n".join(out) + "\n"


def validate(cfg: dict, config_path: Path) -> tuple[list[str], list[str]]:
    """返回 (errors, warnings)。"""
    errors: list[str] = []
    warnings: list[str] = []

    hostname = str(cfg.get("hostname", "")).strip()
    if not hostname:
        errors.append("hostname 不能为空（平台对外访问地址）")

    port = (cfg.get("http") or {}).get("port", 80)
    try:
        port = int(port)
        if not (1 <= port <= 65535):
            raise ValueError
    except (TypeError, ValueError):
        errors.append("http.port 必须是 1-65535 的整数")

    db = cfg.get("database") or {}
    if not str(db.get("name", "")).strip():
        errors.append("database.name 不能为空")
    db_pwd = str(db.get("password", ""))
    if db_pwd and (db_pwd in WEAK_PASSWORDS or len(db_pwd) < MIN_SECRET_LEN):
        warnings.append("database.password 过弱（建议留空自动生成或设置 >= 8 位强密码）")

    redis_pwd = str((cfg.get("redis") or {}).get("password", ""))
    if redis_pwd and (redis_pwd in WEAK_PASSWORDS or len(redis_pwd) < MIN_SECRET_LEN):
        warnings.append("redis.password 过弱（建议留空自动生成或设置 >= 8 位强密码）")

    admin = cfg.get("admin") or {}
    admin_pwd = str(admin.get("password", ""))
    if admin_pwd and admin_pwd in WEAK_PASSWORDS:
        warnings.append("admin.password 使用了常见弱口令，上线前请修改")

    https = cfg.get("https") or {}
    if https.get("enabled"):
        for field, label in (("certificate", "证书"), ("private_key", "私钥")):
            path = str(https.get(field, "")).strip()
            if not path:
                errors.append(f"https.enabled 为真但未配置 https.{field}（{label}路径）")
            elif not Path(path).expanduser().exists():
                errors.append(f"https.{field} 文件不存在: {path}")

    data_dir = str((cfg.get("data") or {}).get("volume_dir", "")).strip()
    if not data_dir:
        errors.append("data.volume_dir 不能为空")

    return errors, warnings


def render_env(cfg: dict, config_path: Path, write_back: bool) -> dict:
    deploy_dir = config_path.parent
    text = config_path.read_text(encoding="utf-8")

    db = cfg.setdefault("database", {})
    redis = cfg.setdefault("redis", {})
    jwt = cfg.setdefault("jwt", {})
    admin = cfg.setdefault("admin", {})
    https = cfg.get("https") or {}

    generated: dict[tuple[str, str], str] = {}
    if not str(db.get("password", "")).strip():
        generated[("database", "password")] = gen_secret()
    if not str(redis.get("password", "")).strip():
        generated[("redis", "password")] = gen_secret()
    if not str(jwt.get("secret_key", "")).strip():
        generated[("jwt", "secret_key")] = gen_secret()
    if not str(admin.get("password", "")).strip():
        generated[("admin", "password")] = gen_secret()

    for (section, key), value in generated.items():
        text = set_yaml_scalar(text, section, key, value)
        (cfg.setdefault(section, {}))[key] = value

    if write_back and generated:
        config_path.write_text(text, encoding="utf-8")
        os.chmod(config_path, 0o600)

    hostname = str(cfg["hostname"]).strip()
    http_port = int((cfg.get("http") or {}).get("port", 80))
    data_dir = str((cfg.get("data") or {})["volume_dir"]).strip()
    if not os.path.isabs(data_dir):
        data_dir = str((deploy_dir / data_dir).resolve())
    os.makedirs(os.path.join(data_dir, "mysql"), exist_ok=True)
    os.makedirs(os.path.join(data_dir, "redis"), exist_ok=True)

    registry = str((cfg.get("image") or {}).get("registry", "")).strip().rstrip("/")
    tag = str((cfg.get("image") or {}).get("tag", "latest")).strip() or "latest"
    backend_image = f"{registry}/ops-monitor-backend:{tag}" if registry else "ops-monitor-backend:local"
    nginx_image = f"{registry}/ops-monitor-nginx:{tag}" if registry else "ops-monitor-nginx:local"

    origin = f"http://{hostname}" + ("" if http_port in (80,) else f":{http_port}")
    env = {
        "HOSTNAME": hostname,
        "HTTP_PORT": str(http_port),
        "HTTPS_ENABLED": "true" if https.get("enabled") else "false",
        "HTTPS_PORT": str((https.get("port") or 443)),
        "HTTPS_CERTIFICATE": str(https.get("certificate", "")).strip(),
        "HTTPS_PRIVATE_KEY": str(https.get("private_key", "")).strip(),
        "DB_NAME": str(db.get("name", "ops_monitor")),
        "DB_PASSWORD": str(db.get("password", "")),
        "REDIS_PASSWORD": str(redis.get("password", "")),
        "JWT_SECRET_KEY": str(jwt.get("secret_key", "")),
        "JWT_EXPIRE_MINUTES": str(jwt.get("expire_minutes", 120)),
        "SEED_ADMIN_USERNAME": str(admin.get("username", "admin")),
        "SEED_ADMIN_PASSWORD": str(admin.get("password", "")),
        "SEED_INIT_DATA": "true" if (cfg.get("seed") or {}).get("init", True) else "false",
        "METRIC_RETENTION_DAYS": str((cfg.get("metrics") or {}).get("retention_days", 7)),
        "OPERATION_LOG_ENABLED": "true" if (cfg.get("operation_log") or {}).get("enabled", True) else "false",
        # 单引号包裹以保留 JSON 内层引号（compose .env 解析会剥离外层单引号）
        "CORS_ORIGINS": "'" + json_dumps_list([origin]) + "'",
        "DATA_VOLUME_DIR": data_dir,
        "IMAGE_REGISTRY": registry,
        "IMAGE_TAG": tag,
        "BACKEND_IMAGE": backend_image,
        "NGINX_IMAGE": nginx_image,
    }
    return env


def json_dumps_list(items: list[str]) -> str:
    import json

    return json.dumps(items)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("config", nargs="?", default="deploy/config.yml")
    parser.add_argument("env_file", nargs="?", default="deploy/.env")
    parser.add_argument("--check", action="store_true", help="仅校验，不写文件")
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.exists():
        print(f"[prepare] 配置文件不存在: {config_path}", file=sys.stderr)
        return 1

    cfg = load_yaml(config_path)
    errors, warnings = validate(cfg, config_path)
    for w in warnings:
        print(f"[warn] {w}")
    if errors:
        for e in errors:
            print(f"[error] {e}", file=sys.stderr)
        return 1
    if args.check:
        print(f"[prepare] 配置校验通过: {config_path}")
        return 0

    env = render_env(cfg, config_path, write_back=True)
    env_path = Path(args.env_file)
    env_path.parent.mkdir(parents=True, exist_ok=True)
    with env_path.open("w", encoding="utf-8") as f:
        f.write("# 本文件由 deploy/prepare.py 自动生成，请勿手动修改\n")
        for key, value in env.items():
            f.write(f"{key}={value}\n")
    os.chmod(env_path, 0o600)
    print(f"[prepare] 已渲染 {env_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
