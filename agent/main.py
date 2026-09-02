"""轻量级服务器运维监控平台 - Linux Agent 主程序。"""

from __future__ import annotations

import signal
import threading
import time

from agent.collector import collect_assets, collect_metrics, collect_system_info
from agent.collector.service import collect_services
from agent.config.config import AgentConfig, load_config
from agent.reporter.client import AgentClient
from agent.reporter.report import (
    register,
    send_assets,
    send_heartbeat,
    send_metrics,
    send_services,
)
from agent.utils.logger import setup_logger

AGENT_VERSION = "1.0.0"


class Agent:
    """Agent 主控：注册后按周期并行执行心跳、指标与资产上报。"""

    def __init__(self, config: AgentConfig) -> None:
        self.config = config
        self.logger = setup_logger(config.log.level, config.log.file)
        self._stop = threading.Event()
        self.server_id: int | None = None
        self._client = AgentClient(
            base_url=config.server.url,
            token=config.server.token,
            timeout=config.collect.request_timeout,
            retry_max_seconds=config.collect.retry_max_seconds,
        )

    def run(self) -> None:
        """启动 Agent：注册成功后并行启动三个上报循环，阻塞至收到停止信号。"""
        self._register()

        threads = [
            threading.Thread(target=self._heartbeat_loop, name="heartbeat", daemon=True),
            threading.Thread(target=self._metrics_loop, name="metrics", daemon=True),
            threading.Thread(target=self._assets_loop, name="assets", daemon=True),
        ]
        for t in threads:
            t.start()

        self.logger.info("Agent 已启动，server_id=%s", self.server_id)
        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)

        while not self._stop.is_set():
            self._stop.wait(1)

        self.logger.info("Agent 正在停止...")
        self._client.close()

    def _register(self) -> None:
        """注册并获取 server_id（失败时指数退避重试）。"""
        delay = 1.0
        while True:
            try:
                result = register(
                    self._client,
                    server_code=self.config.server.server_code,
                    token=self.config.server.token,
                    system_info=collect_system_info(),
                    agent_version=AGENT_VERSION,
                )
                self.server_id = result["server_id"]
                self.logger.info("注册成功，server_id=%s", self.server_id)
                return
            except Exception as exc:
                self.logger.warning("注册失败: %s，%ss 后重试", exc, delay)
                time.sleep(delay)
                delay = min(delay * 2, self.config.collect.retry_max_seconds)

    def _heartbeat_loop(self) -> None:
        while not self._stop.is_set():
            try:
                send_heartbeat(
                    self._client,
                    server_id=self.server_id,
                    agent_version=AGENT_VERSION,
                )
            except Exception as exc:
                self.logger.warning("心跳上报失败: %s", exc)
            self._sleep_interval(self.config.collect.heartbeat_interval)

    def _metrics_loop(self) -> None:
        while not self._stop.is_set():
            try:
                send_metrics(
                    self._client,
                    server_id=self.server_id,
                    metrics=collect_metrics(),
                )
            except Exception as exc:
                self.logger.warning("指标上报失败: %s", exc)
            self._sleep_interval(self.config.collect.metrics_interval)

    def _assets_loop(self) -> None:
        while not self._stop.is_set():
            try:
                send_assets(
                    self._client,
                    server_id=self.server_id,
                    assets=collect_assets(),
                )
                send_services(
                    self._client,
                    server_id=self.server_id,
                    services=collect_services(self.config.collect.services),
                )
            except Exception as exc:
                self.logger.warning("资产/服务同步失败: %s", exc)
            self._sleep_interval(self.config.collect.assets_interval)

    def _sleep_interval(self, seconds: int) -> None:
        self._stop.wait(seconds)

    def _handle_signal(self, signum, frame) -> None:
        self.logger.info("收到信号 %s，准备退出", signum)
        self._stop.set()


def main() -> None:
    config = load_config()
    Agent(config).run()


if __name__ == "__main__":
    main()
