"""System integration helpers for boot and resume application."""

from __future__ import annotations

import shlex
from pathlib import Path

SERVICE_PATH = Path("/etc/systemd/system/ryzenadj-control.service")
HOOK_PATH = Path("/usr/lib/systemd/system-sleep/ryzenadj-control-resume")
REAPPLY_SERVICE_PATH = Path("/etc/systemd/system/ryzenadj-control-reapply.service")
REAPPLY_TIMER_PATH = Path("/etc/systemd/system/ryzenadj-control-reapply.timer")

REAPPLY_INTERVAL_MIN = 5
REAPPLY_INTERVAL_MAX = 3600
REAPPLY_INTERVAL_DEFAULT = 30


class SystemdManager:
    """Create or remove systemd resources for persistent profile application."""

    @staticmethod
    def _quoted_command(command: list[str]) -> str:
        return shlex.join(command)

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
        quoted = self._quoted_command(command)
        return "\n".join(
            [
                "#!/usr/bin/env bash",
                "if [ \"$1\" = \"post\" ]; then",
                f"  {quoted}",
                "fi",
                "",
            ]
        )

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
