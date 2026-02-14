"""Command construction and asynchronous command execution."""

from __future__ import annotations

import os
import shlex
import subprocess
from collections.abc import Callable

from PyQt6.QtCore import QObject, QThread, pyqtSignal

from core.options import BOOLEAN_OPTIONS, NUMERIC_OPTIONS


def build_ryzenadj_command(values: dict, binary: str = "ryzenadj") -> list[str]:
    """Build a ryzenadj command from profile values.

    Numeric parameters are only included when their *_enabled flag is true.
    """
    command = [binary]

    for spec in NUMERIC_OPTIONS:
        if not bool(values.get(f"{spec.key}_enabled", False)):
            continue
        value = int(values.get(spec.key, 0))
        command.extend([spec.cli, str(value)])

    for option in BOOLEAN_OPTIONS:
        if bool(values.get(option["key"], False)):
            command.append(option["cli"])

    return command


class CommandWorker(QObject):
    """Worker object used inside a QThread for subprocess execution."""

    completed = pyqtSignal(bool, str, str, str)

    def __init__(self, command: list[str]) -> None:
        super().__init__()
        self.command = command

    def run(self) -> None:
        cmd_display = shlex.join(self.command)
        try:
            proc = subprocess.run(
                self.command,
                check=False,
                capture_output=True,
                text=True,
            )
            stdout = proc.stdout.strip()
            stderr = proc.stderr.strip()
            success = proc.returncode == 0
            if proc.returncode == 127:
                stderr = stderr or "Command not found. Is ryzenadj installed?"
        except FileNotFoundError:
            success = False
            stdout = ""
            stderr = "Command not found. Is ryzenadj installed?"
        except Exception as exc:  # pragma: no cover
            success = False
            stdout = ""
            stderr = str(exc)

        self.completed.emit(success, stdout, stderr, cmd_display)


class CommandExecutor(QObject):
    """Manage asynchronous subprocess tasks."""

    def __init__(self) -> None:
        super().__init__()
        self._active_threads: list[QThread] = []
        self._active_workers: list[CommandWorker] = []

    def _prepend_privilege(self, command: list[str], use_pkexec: bool) -> list[str]:
        if os.geteuid() == 0:
            return command
        if use_pkexec:
            return ["pkexec", *command]
        return command

    def run_async(
        self,
        command: list[str],
        use_pkexec: bool,
        callback: Callable[[bool, str, str, str], None],
    ) -> None:
        final_command = self._prepend_privilege(command, use_pkexec)
        self._spawn_worker(final_command, callback)

    def run_shell_async(
        self,
        script: str,
        use_pkexec: bool,
        callback: Callable[[bool, str, str, str], None],
    ) -> None:
        command = ["/usr/bin/bash", "-lc", script]
        final_command = self._prepend_privilege(command, use_pkexec)
        self._spawn_worker(final_command, callback)

    def _spawn_worker(
        self,
        command: list[str],
        callback: Callable[[bool, str, str, str], None],
    ) -> None:
        thread = QThread()
        worker = CommandWorker(command)
        worker.moveToThread(thread)

        thread.started.connect(worker.run)
        worker.completed.connect(callback)
        worker.completed.connect(thread.quit)
        worker.completed.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)

        def _cleanup() -> None:
            if thread in self._active_threads:
                self._active_threads.remove(thread)
            if worker in self._active_workers:
                self._active_workers.remove(worker)

        thread.finished.connect(_cleanup)

        self._active_threads.append(thread)
        self._active_workers.append(worker)
        thread.start()
