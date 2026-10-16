"""System integration helpers for boot, resume and periodic application.

Uses systemd when it is the running init system, otherwise cron (/etc/cron.d)
plus elogind sleep hooks.
"""

from __future__ import annotations

import shlex
import shutil
import subprocess
from pathlib import Path

SERVICE_PATH = Path("/etc/systemd/system/ryzenadj-control.service")
HOOK_PATH = Path("/usr/lib/systemd/system-sleep/ryzenadj-control-resume")
REAPPLY_SERVICE_PATH = Path("/etc/systemd/system/ryzenadj-control-reapply.service")
REAPPLY_TIMER_PATH = Path("/etc/systemd/system/ryzenadj-control-reapply.timer")

CRON_PATH = Path("/etc/cron.d/ryzenadj-control")
ELOGIND_SLEEP_DIRS = (
    Path("/usr/lib/elogind/system-sleep"),
    Path("/lib64/elogind/system-sleep"),
    Path("/lib/elogind/system-sleep"),
    Path("/etc/elogind/system-sleep"),
)
RESUME_HOOK_NAME = "ryzenadj-control-resume"

REAPPLY_INTERVAL_MIN = 5
REAPPLY_INTERVAL_MAX = 3600
REAPPLY_INTERVAL_DEFAULT = 30


def detect_integration_manager() -> SystemdManager | CronManager | None:
    """Return the integration backend for this system, or None if none is usable."""
    if shutil.which("systemctl") and Path("/run/systemd/system").is_dir():
        return SystemdManager()
    if Path("/etc/cron.d").is_dir():
        return CronManager()
    return None


def build_sleep_hook_content(command: list[str]) -> str:
    """Sleep hook script; systemd-sleep and elogind call it with pre/post."""
    return "\n".join(
        [
            "#!/bin/sh",
            "if [ \"$1\" = \"post\" ]; then",
            f"  {shlex.join(command)}",
            "fi",
            "",
        ]
    )


class SystemdManager:
    """Create or remove systemd resources for persistent profile application."""

    description = "systemd (service, sleep hook, timer)"
    resume_available = True
    interval_suffix = " s"
    interval_min = REAPPLY_INTERVAL_MIN
    interval_max = REAPPLY_INTERVAL_MAX
    interval_default = REAPPLY_INTERVAL_DEFAULT

    @staticmethod
    def _quoted_command(command: list[str]) -> str:
        return shlex.join(command)

    @staticmethod
    def _is_unit_enabled(unit: str) -> bool:
        try:
            proc = subprocess.run(
                ["systemctl", "is-enabled", unit],
                check=False,
                capture_output=True,
                text=True,
            )
            return proc.returncode == 0 and proc.stdout.strip() == "enabled"
        except OSError:
            return False

    def is_boot_enabled(self) -> bool:
        return self._is_unit_enabled("ryzenadj-control.service")

    def is_resume_enabled(self) -> bool:
        return HOOK_PATH.exists()

    def is_reapply_enabled(self) -> bool:
        return self._is_unit_enabled("ryzenadj-control-reapply.timer")

    def installed_reapply_interval(self) -> int | None:
        try:
            content = REAPPLY_TIMER_PATH.read_text(encoding="utf-8")
        except OSError:
            return None
        for line in content.splitlines():
            key, _, value = line.partition("=")
            if key.strip() == "OnUnitActiveSec" and value.strip().endswith("s"):
                try:
                    interval = int(value.strip()[:-1])
                except ValueError:
                    return None
                if self.interval_min <= interval <= self.interval_max:
                    return interval
                return None
        return None

    def build_service_content(self, command: list[str]) -> str:
        quoted = self._quoted_command(command)
        return "\n".join(
            [
                "[Unit]",
                "Description=Apply ryzenadj profile (ryzenadj-control)",
                "After=multi-user.target",
                "",
                "[Service]",
                "Type=oneshot",
                f"ExecStart={quoted}",
                "",
                "[Install]",
                "WantedBy=multi-user.target",
                "",
            ]
        )

    def build_reapply_service_content(self, command: list[str]) -> str:
        quoted = self._quoted_command(command)
        return "\n".join(
            [
                "[Unit]",
                "Description=Periodically re-apply ryzenadj profile (ryzenadj-control)",
                "",
                "[Service]",
                "Type=oneshot",
                f"ExecStart={quoted}",
                "StandardOutput=null",
                "LogLevelMax=warning",
                "",
            ]
        )

    def build_reapply_timer_content(self, interval_seconds: int) -> str:
        if not REAPPLY_INTERVAL_MIN <= interval_seconds <= REAPPLY_INTERVAL_MAX:
            raise ValueError(
                f"Re-apply interval must be between {REAPPLY_INTERVAL_MIN} "
                f"and {REAPPLY_INTERVAL_MAX} seconds"
            )
        return "\n".join(
            [
                "[Unit]",
                "Description=Periodically re-apply ryzenadj profile (ryzenadj-control)",
                "",
                "[Timer]",
                f"OnBootSec={interval_seconds}s",
                f"OnUnitActiveSec={interval_seconds}s",
                "AccuracySec=1s",
                "",
                "[Install]",
                "WantedBy=timers.target",
                "",
            ]
        )

    def build_sleep_hook_content(self, command: list[str]) -> str:
        return build_sleep_hook_content(command)

    def build_sync_script(
        self,
        command: list[str],
        enable_boot: bool,
        enable_resume: bool,
        enable_reapply: bool = False,
        reapply_interval: int = REAPPLY_INTERVAL_DEFAULT,
    ) -> str:
        """Generate a shell script that applies selected integration state."""
        service_content = self.build_service_content(command)
        hook_content = self.build_sleep_hook_content(command)

        script_lines = [
            "set -euo pipefail",
            "mkdir -p /etc/systemd/system",
            "mkdir -p /usr/lib/systemd/system-sleep",
        ]

        if enable_boot:
            quoted_service = shlex.quote(service_content)
            script_lines.extend(
                [
                    f"printf '%s' {quoted_service} > {SERVICE_PATH}",
                    "chmod 644 /etc/systemd/system/ryzenadj-control.service",
                    "systemctl daemon-reload",
                    "systemctl enable ryzenadj-control.service",
                    "systemctl restart ryzenadj-control.service || true",
                ]
            )
        else:
            script_lines.extend(
                [
                    "systemctl disable ryzenadj-control.service || true",
                    "rm -f /etc/systemd/system/ryzenadj-control.service",
                    "systemctl daemon-reload",
                ]
            )

        if enable_resume:
            quoted_hook = shlex.quote(hook_content)
            script_lines.extend(
                [
                    f"printf '%s' {quoted_hook} > {HOOK_PATH}",
                    "chmod 755 /usr/lib/systemd/system-sleep/ryzenadj-control-resume",
                ]
            )
        else:
            script_lines.append("rm -f /usr/lib/systemd/system-sleep/ryzenadj-control-resume")

        if enable_reapply:
            quoted_reapply_service = shlex.quote(self.build_reapply_service_content(command))
            quoted_reapply_timer = shlex.quote(self.build_reapply_timer_content(reapply_interval))
            script_lines.extend(
                [
                    f"printf '%s' {quoted_reapply_service} > {REAPPLY_SERVICE_PATH}",
                    f"printf '%s' {quoted_reapply_timer} > {REAPPLY_TIMER_PATH}",
                    f"chmod 644 {REAPPLY_SERVICE_PATH} {REAPPLY_TIMER_PATH}",
                    "systemctl daemon-reload",
                    "systemctl enable ryzenadj-control-reapply.timer",
                    "systemctl restart ryzenadj-control-reapply.timer || true",
                ]
            )
        else:
            script_lines.extend(
                [
                    "systemctl disable --now ryzenadj-control-reapply.timer || true",
                    f"rm -f {REAPPLY_SERVICE_PATH} {REAPPLY_TIMER_PATH}",
                    "systemctl daemon-reload",
                ]
            )

        return "\n".join(script_lines)

    def build_boot_script(self, command: list[str], enable_boot: bool) -> str:
        """Generate a shell script for boot service only."""
        service_content = self.build_service_content(command)
        script_lines = [
            "set -euo pipefail",
            "mkdir -p /etc/systemd/system",
        ]

        if enable_boot:
            quoted_service = shlex.quote(service_content)
            script_lines.extend(
                [
                    f"printf '%s' {quoted_service} > {SERVICE_PATH}",
                    "chmod 644 /etc/systemd/system/ryzenadj-control.service",
                    "systemctl daemon-reload",
                    "systemctl enable ryzenadj-control.service",
                    "systemctl restart ryzenadj-control.service || true",
                ]
            )
        else:
            script_lines.extend(
                [
                    "systemctl disable ryzenadj-control.service || true",
                    "rm -f /etc/systemd/system/ryzenadj-control.service",
                    "systemctl daemon-reload",
                ]
            )

        return "\n".join(script_lines)

    def build_resume_script(self, command: list[str], enable_resume: bool) -> str:
        """Generate a shell script for resume hook only."""
        hook_content = self.build_sleep_hook_content(command)
        script_lines = [
            "set -euo pipefail",
            "mkdir -p /usr/lib/systemd/system-sleep",
        ]

        if enable_resume:
            quoted_hook = shlex.quote(hook_content)
            script_lines.extend(
                [
                    f"printf '%s' {quoted_hook} > {HOOK_PATH}",
                    "chmod 755 /usr/lib/systemd/system-sleep/ryzenadj-control-resume",
                ]
            )
        else:
            script_lines.append("rm -f /usr/lib/systemd/system-sleep/ryzenadj-control-resume")

        return "\n".join(script_lines)


class CronManager:
    """Boot and periodic application via /etc/cron.d, resume via elogind sleep hooks.

    Used on systems without systemd (e.g. OpenRC). Requires a cron daemon that
    reads /etc/cron.d (cronie, vixie-cron). Cron cannot run more often than once
    per minute, so the re-apply interval is in minutes.
    """

    resume_available: bool
    interval_suffix = " min"
    interval_min = 1
    interval_max = 59
    interval_default = 1

    def __init__(self) -> None:
        self.sleep_dir = self._find_elogind_sleep_dir()
        self.resume_available = self.sleep_dir is not None
        resume = f", elogind ({self.sleep_dir})" if self.sleep_dir else ""
        self.description = f"cron ({CRON_PATH}){resume}"

    @staticmethod
    def _find_elogind_sleep_dir() -> Path | None:
        for directory in ELOGIND_SLEEP_DIRS:
            if directory.is_dir():
                return directory
        if Path("/etc/elogind").is_dir():
            return Path("/etc/elogind/system-sleep")
        return None

    def _hook_path(self) -> Path | None:
        return self.sleep_dir / RESUME_HOOK_NAME if self.sleep_dir else None

    @staticmethod
    def _cron_lines() -> list[str]:
        try:
            return CRON_PATH.read_text(encoding="utf-8").splitlines()
        except OSError:
            return []

    def is_boot_enabled(self) -> bool:
        return any(line.startswith("@reboot ") for line in self._cron_lines())

    def is_resume_enabled(self) -> bool:
        hook_path = self._hook_path()
        return bool(hook_path and hook_path.exists())

    def is_reapply_enabled(self) -> bool:
        return self.installed_reapply_interval() is not None

    def installed_reapply_interval(self) -> int | None:
        for line in self._cron_lines():
            if not line.startswith("*/"):
                continue
            try:
                interval = int(line.split()[0][2:])
            except (IndexError, ValueError):
                return None
            if self.interval_min <= interval <= self.interval_max:
                return interval
            return None
        return None

    def build_cron_content(
        self,
        command: list[str],
        enable_boot: bool,
        enable_reapply: bool,
        interval_minutes: int,
    ) -> str:
        quoted = shlex.join(command)
        if "%" in quoted:
            raise ValueError("Command must not contain '%' (special character in cron)")
        if not self.interval_min <= interval_minutes <= self.interval_max:
            raise ValueError(
                f"Re-apply interval must be between {self.interval_min} "
                f"and {self.interval_max} minutes"
            )
        lines = [
            "# Managed by ryzenadj-control. Manual changes are overwritten.",
            "SHELL=/bin/sh",
            "PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        ]
        if enable_boot:
            lines.append(f"@reboot root {quoted}")
        if enable_reapply:
            lines.append(f"*/{interval_minutes} * * * * root {quoted} >/dev/null 2>&1")
        return "\n".join(lines) + "\n"

    def build_sync_script(
        self,
        command: list[str],
        enable_boot: bool,
        enable_resume: bool,
        enable_reapply: bool = False,
        reapply_interval: int = 1,
    ) -> str:
        """Generate a shell script that applies selected integration state."""
        script_lines = ["set -euo pipefail"]

        if enable_boot or enable_reapply:
            cron_content = self.build_cron_content(
                command, enable_boot, enable_reapply, reapply_interval
            )
            script_lines.extend(
                [
                    f"printf '%s' {shlex.quote(cron_content)} > {CRON_PATH}",
                    f"chmod 644 {CRON_PATH}",
                ]
            )
        else:
            script_lines.append(f"rm -f {CRON_PATH}")

        hook_path = self._hook_path()
        if hook_path:
            if enable_resume:
                quoted_hook = shlex.quote(build_sleep_hook_content(command))
                script_lines.extend(
                    [
                        f"mkdir -p {self.sleep_dir}",
                        f"printf '%s' {quoted_hook} > {hook_path}",
                        f"chmod 755 {hook_path}",
                    ]
                )
            else:
                script_lines.append(f"rm -f {hook_path}")

        return "\n".join(script_lines)
