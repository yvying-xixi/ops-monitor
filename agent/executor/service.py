"""受控服务执行器：执行 systemctl 操作与 journalctl 日志，带白名单校验。"""

from __future__ import annotations

import subprocess

ALLOWED_ACTIONS = ("STATUS", "START", "STOP", "RESTART")
ACTION_COMMANDS = {
    "STATUS": ["systemctl", "is-active"],
    "START": ["systemctl", "start"],
    "STOP": ["systemctl", "stop"],
    "RESTART": ["systemctl", "restart"],
}
LOG_LINES_DEFAULT = 200


class ServiceExecutor:
    """服务执行器。

    安全约束：
    - 服务名必须在白名单内，否则拒绝执行。
    - 操作类型仅限 STATUS/START/STOP/RESTART。
    - 一律使用 subprocess 参数列表，禁止拼接 shell 命令。
    """

    def __init__(self, allowed_services: list[str]) -> None:
        self._allowed = set(allowed_services)

    def validate(self, service: str, action: str) -> None:
        """校验服务名与操作类型。

        Raises:
            ValueError: 服务不在白名单或操作类型非法。
        """
        if service not in self._allowed:
            raise ValueError(f"服务 {service} 不在白名单内，拒绝执行")
        if action not in ALLOWED_ACTIONS:
            raise ValueError(f"不允许的操作类型: {action}")

    def run_action(self, service: str, action: str, timeout: float = 60) -> tuple[bool, str]:
        """执行受控操作，返回 (是否成功, 输出文本)。

        Args:
            service: 服务名（须在白名单内）。
            action: 操作类型。
            timeout: 超时（秒）。

        Returns:
            (success, output)。
        """
        self.validate(service, action)
        command = [*ACTION_COMMANDS[action], service]
        try:
            result = subprocess.run(
                command, capture_output=True, text=True, timeout=timeout
            )
        except subprocess.TimeoutExpired:
            return False, f"执行超时（{int(timeout)}s）"
        except OSError as exc:
            return False, f"执行失败: {exc}"

        if action == "STATUS":
            success = result.returncode == 0
        else:
            success = result.returncode == 0

        if success:
            output = (result.stdout or "").strip()
        else:
            output = (result.stderr or result.stdout or "").strip()
        return success, output

    def fetch_logs(self, service: str, lines: int = LOG_LINES_DEFAULT) -> tuple[bool, str]:
        """抓取服务最近日志。

        Args:
            service: 服务名（须在白名单内）。
            lines: 日志行数。

        Returns:
            (success, 日志文本)。
        """
        self.validate(service, "STATUS")
        command = ["journalctl", "-n", str(lines), "-u", service, "--no-pager"]
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=30)
        except (subprocess.SubprocessError, OSError) as exc:
            return False, f"获取日志失败: {exc}"
        return result.returncode == 0, (result.stdout or result.stderr or "").strip()
