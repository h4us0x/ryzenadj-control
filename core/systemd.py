"""System integration helpers for boot and resume application."""

from __future__ import annotations

import shlex
from pathlib import Path

SERVICE_PATH = Path("/etc/systemd/system/ryzenadj-control.service")
HOOK_PATH = Path("/usr/lib/systemd/system-sleep/ryzenadj-control-resume")


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
