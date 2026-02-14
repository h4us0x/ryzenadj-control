"""Main application window for ryzenadj-gui."""

from __future__ import annotations

import subprocess
import shlex
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QAction, QPalette
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QStackedWidget,
    QStatusBar,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from core.executor import CommandExecutor, build_ryzenadj_command
from core.monitor import parse_info_output, parse_profile_values_from_info
from core.options import BOOLEAN_OPTIONS, NUMERIC_OPTIONS, default_profile_values, options_by_category
from core.profiles import ProfileError, ProfileManager
from core.systemd import SystemdManager


class CollapsibleBox(QWidget):
    """Simple collapsible container."""

    def __init__(self, title: str) -> None:
        super().__init__()
        self.toggle = QToolButton(text=title, checkable=True, checked=True)
        self.toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.toggle.setArrowType(Qt.ArrowType.DownArrow)
        self.toggle.clicked.connect(self._on_toggled)

        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(8, 4, 8, 8)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.toggle)
        layout.addWidget(self.content)

    def _on_toggled(self, checked: bool) -> None:
        self.toggle.setArrowType(Qt.ArrowType.DownArrow if checked else Qt.ArrowType.RightArrow)
        self.content.setVisible(checked)


class OptionControl(QWidget):
    """Slider + spinbox + enable checkbox for numeric ryzenadj options."""

    def __init__(
        self,
        label: str,
        minimum: int,
        maximum: int,
        default: int,
        tooltip: str,
        ui_scale: int = 1,
        ui_suffix: str = "",
    ) -> None:
        super().__init__()
        self.ui_scale = max(1, int(ui_scale))

        name_label = QLabel(label)
        name_label.setToolTip(tooltip)

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(self._to_display(minimum), self._to_display(maximum))
        self.slider.setValue(self._to_display(default))
        self.slider.setToolTip(tooltip)

        self.spin = QSpinBox()
        self.spin.setRange(self._to_display(minimum), self._to_display(maximum))
        self.spin.setValue(self._to_display(default))
        self.spin.setSuffix(ui_suffix)
        self.spin.setToolTip(tooltip)

        self.enable_checkbox = QCheckBox("Active")
        self.enable_checkbox.setChecked(False)
        self.enable_checkbox.setToolTip("Enable this setting for Apply")
        self.enable_checkbox.toggled.connect(self._sync_enabled_state)

        self.slider.valueChanged.connect(self.spin.setValue)
        self.spin.valueChanged.connect(self.slider.setValue)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(self.enable_checkbox)
        layout.addWidget(name_label, 2)
        layout.addWidget(self.slider, 4)
        self.spin.setFixedWidth(96)
        layout.addWidget(self.spin)

        self._sync_enabled_state(False)

    def value(self) -> int:
        return self._to_raw(self.spin.value())

    def set_value(self, value: int) -> None:
        self.spin.setValue(self._to_display(value))

    def is_enabled(self) -> bool:
        return self.enable_checkbox.isChecked()

    def set_option_enabled(self, enabled: bool) -> None:
        self.enable_checkbox.setChecked(enabled)

    def _sync_enabled_state(self, enabled: bool) -> None:
        self.slider.setEnabled(enabled)
        self.spin.setEnabled(enabled)

    def _to_display(self, raw_value: int) -> int:
        return int(raw_value) // self.ui_scale

    def _to_raw(self, display_value: int) -> int:
        return int(display_value) * self.ui_scale


class MainWindow(QMainWindow):
    """Main GUI composition and actions."""
    INITIAL_DEFAULT_PROFILE_NAME = "Initial Default"
    WARNING_PATTERNS = (
        "not supported on this family",
        "is not supported",
    )
    FATAL_PATTERNS = (
        "permission denied",
        "command not found",
        "no such file",
        "failed to",
        "traceback",
        "unable to",
        "polkit",
        "authentication",
    )

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("RyzenAdj GUI")
        self.resize(860, 560)
        self.setMinimumSize(860, 560)

        self.profile_manager = ProfileManager()
        self.executor = CommandExecutor()
        self.systemd_manager = SystemdManager()

        self.current_data: dict = {}
        self.option_controls: dict[str, OptionControl] = {}
        self.boolean_controls: dict[str, QCheckBox] = {}
        self.monitor_labels: dict[str, QLabel] = {}
        self.save_button: QPushButton | None = None
        self.delete_button: QPushButton | None = None
        self.initial_default_button: QPushButton | None = None
        self.reset_button: QPushButton | None = None
        self.apply_boot_checkbox: QCheckBox | None = None
        self.apply_resume_checkbox: QCheckBox | None = None
        self.start_gui_on_login_checkbox: QCheckBox | None = None
        self.auto_sync_integration_checkbox: QCheckBox | None = None

        self._init_ui()
        self._load_profiles_on_startup()

    def _init_ui(self) -> None:
        self._build_menu()

        root = QWidget()
        self.setCentralWidget(root)
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(10, 10, 10, 8)
        root_layout.setSpacing(8)

        root_layout.addWidget(self._build_profile_bar())

        split_layout = QHBoxLayout()
        split_layout.setSpacing(10)
        root_layout.addLayout(split_layout, 1)

        self.pages = QStackedWidget()
        self.nav_list = QListWidget()
        self.nav_list.setMaximumWidth(170)
        self.nav_list.currentRowChanged.connect(self.pages.setCurrentIndex)
        split_layout.addWidget(self.nav_list)
        split_layout.addWidget(self.pages, 1)

        self._build_pages()

        output_group = CollapsibleBox("Command Output")
        output_layout = output_group.content_layout
        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        self.output_text.setMaximumHeight(120)
        self.output_text.setPlaceholderText("Command details appear here...")
        output_layout.addWidget(self.output_text)
        root_layout.addWidget(output_group)

        self.status_text = QLabel("Ready")
        self.status_timestamp = QLabel("-")
        status = QStatusBar()
        status.addWidget(self.status_text, 2)
        status.addPermanentWidget(self.status_timestamp)
        self.setStatusBar(status)

        self._apply_palette_adaptation()

    def _build_profile_bar(self) -> QWidget:
        bar = QWidget()
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(6)

        self.profile_dropdown = QComboBox()
        self.profile_dropdown.setEditable(True)
        self.profile_dropdown.lineEdit().setPlaceholderText("Type profile name...")
        self.profile_dropdown.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.profile_dropdown.setMinimumWidth(240)
        self.profile_dropdown.currentTextChanged.connect(self._update_profile_action_state)
        self.profile_dropdown.currentTextChanged.connect(self.on_profile_selected)
        layout.addWidget(QLabel("Profile:"))
        layout.addWidget(self.profile_dropdown, 1)

        self.apply_button = QPushButton("Apply")
        self.apply_button.clicked.connect(self.apply_current_values)
        layout.addWidget(self.apply_button)

        self.save_button = QPushButton("Save")
        self.save_button.clicked.connect(self.save_current_profile)
        layout.addWidget(self.save_button)

        self.delete_button = QPushButton("Delete")
        self.delete_button.clicked.connect(self.delete_selected_profile)
        layout.addWidget(self.delete_button)

        self.reset_button = QPushButton("Reset to Default")
        self.reset_button.clicked.connect(self.reset_to_defaults)
        self.reset_button.setEnabled(False)
        self.reset_button.setToolTip(
            "Disabled until 'Set Initial Default' has captured machine baseline values."
        )
        layout.addWidget(self.reset_button)

        self.initial_default_button = QPushButton("Set Initial Default")
        self.initial_default_button.setToolTip(
            "Create/update a read-only profile from current machine defaults via 'ryzenadj --info'."
        )
        self.initial_default_button.clicked.connect(self.capture_initial_default_profile)
        layout.addWidget(self.initial_default_button)

        return bar

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("File")

        import_action = QAction("Import Profiles", self)
        import_action.triggered.connect(self.import_profiles)
        file_menu.addAction(import_action)

        export_action = QAction("Export Profiles", self)
        export_action.triggered.connect(self.export_profiles)
        file_menu.addAction(export_action)

    def _build_pages(self) -> None:
        self._add_page("Home", self._build_profiles_page())

        categories = options_by_category()
        self._add_page("Power", self._build_option_page(categories["Power"]))
        self._add_page("Current", self._build_option_page(categories["Current"]))
        self._add_page("Clocks", self._build_option_page(categories["Clocks"]))
        self._add_page("Advanced", self._build_advanced_page(categories["Advanced"]))
        self._add_page("System", self._build_system_page())
        self._add_page("Monitoring", self._build_monitor_page())

        self.nav_list.setCurrentRow(0)

    def _add_page(self, title: str, widget: QWidget) -> None:
        self.nav_list.addItem(QListWidgetItem(title))
        self.pages.addWidget(widget)

    def _build_profiles_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(10)

        description = QLabel(
            "RyzenAdj GUI lets you tune platform power, current and clock limits through profiles.\n\n"
            "Recommended workflow:\n"
            "1. Right after a clean boot, click 'Set Initial Default'.\n"
            "   This captures your machine's current baseline from 'ryzenadj --info' into a read-only profile.\n"
            "2. Create your own profile name at the top bar, tune only needed options, then click Save.\n"
            "3. Click Apply to execute the generated ryzenadj command.\n"
            "4. Use Reset to Default to restore the captured baseline values.\n\n"
            "Important notes:\n"
            "- Reset to Default is available only after Initial Default was captured.\n"
            "- Initial Default is read-only and cannot be edited or deleted.\n"
            "- Import/Export is available via File menu.\n\n"
            "Risk notice:\n"
            "Aggressive limits can cause instability, thermal stress or shutdowns. "
            "Change values gradually and monitor temperatures under load."
        )
        description.setWordWrap(True)
        layout.addWidget(description)

        layout.addStretch(1)
        return page

    def _build_option_page(self, options: list) -> QWidget:
        container = QWidget()
        vlayout = QVBoxLayout(container)
        vlayout.setContentsMargins(0, 0, 0, 0)
        vlayout.setSpacing(4)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

        inner = QWidget()
        inner_layout = QVBoxLayout(inner)
        inner_layout.setContentsMargins(6, 6, 6, 6)
        inner_layout.setSpacing(4)

        for spec in options:
            control = OptionControl(
                spec.label,
                spec.minimum,
                spec.maximum,
                spec.default,
                spec.tooltip,
                spec.ui_scale,
                spec.ui_suffix,
            )
            self.option_controls[spec.key] = control
            inner_layout.addWidget(control)

        inner_layout.addStretch(1)
        scroll.setWidget(inner)

        vlayout.addWidget(scroll)
        return container

    def _build_advanced_page(self, numeric_options: list) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(6)

        thermal_box = QGroupBox("Thermal & Ramp")
        thermal_layout = QVBoxLayout(thermal_box)
        for spec in numeric_options:
            control = OptionControl(
                spec.label,
                spec.minimum,
                spec.maximum,
                spec.default,
                spec.tooltip,
                spec.ui_scale,
                spec.ui_suffix,
            )
            self.option_controls[spec.key] = control
            thermal_layout.addWidget(control)
        layout.addWidget(thermal_box)

        mode_box = QGroupBox("Mode Flags")
        mode_layout = QVBoxLayout(mode_box)
        for item in BOOLEAN_OPTIONS:
            checkbox = QCheckBox(item["label"])
            checkbox.setToolTip(item["tooltip"])
            self.boolean_controls[item["key"]] = checkbox
            mode_layout.addWidget(checkbox)
        self._wire_mutually_exclusive_mode_flags()
        layout.addWidget(mode_box)

        layout.addStretch(1)
        return page

    def _build_system_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        settings_group = QGroupBox("Execution & Privileges")
        form = QFormLayout(settings_group)

        self.use_pkexec_checkbox = QCheckBox("Run privileged commands through pkexec")
        self.use_pkexec_checkbox.setChecked(True)
        form.addRow("Privilege mode:", self.use_pkexec_checkbox)

        hint = QLabel(
            "pkexec is recommended for applying settings and creating system files "
            "without running the full app as root."
        )
        hint.setWordWrap(True)
        form.addRow("", hint)

        layout.addWidget(settings_group)

        integration_group = QGroupBox("System Integration")
        integration_layout = QVBoxLayout(integration_group)
        self.apply_boot_checkbox = QCheckBox("Apply selected profile at system boot")
        self.apply_resume_checkbox = QCheckBox("Re-apply selected profile after resume")
        self.start_gui_on_login_checkbox = QCheckBox("Start RyzenAdj GUI automatically after login")
        self.auto_sync_integration_checkbox = QCheckBox(
            "Automatically update active boot/resume integration after profile switch"
        )
        self.auto_sync_integration_checkbox.setChecked(True)
        integration_layout.addWidget(self.apply_boot_checkbox)
        integration_layout.addWidget(self.apply_resume_checkbox)
        integration_layout.addWidget(self.start_gui_on_login_checkbox)
        integration_layout.addWidget(self.auto_sync_integration_checkbox)

        integration_button = QPushButton("Apply Integration")
        integration_button.clicked.connect(self.apply_system_integration)
        integration_layout.addWidget(integration_button)
        layout.addWidget(integration_group)

        layout.addStretch(1)
        return page

    def _build_monitor_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(8)

        grid = QGridLayout()
        labels = {
            "stapm": "Current STAPM",
            "ppt_fast": "Current PPT Fast",
            "ppt_slow": "Current PPT Slow",
            "cpu_temp": "CPU Temp",
            "power_draw": "Current Power Draw",
        }

        row = 0
        for key, text in labels.items():
            label = QLabel("N/A")
            label.setFrameStyle(QFrame.Shape.Panel | QFrame.Shadow.Sunken)
            label.setMinimumHeight(28)
            grid.addWidget(QLabel(text + ":"), row, 0)
            grid.addWidget(label, row, 1)
            self.monitor_labels[key] = label
            row += 1

        layout.addLayout(grid)

        controls = QHBoxLayout()
        refresh_button = QPushButton("Refresh Now")
        refresh_button.clicked.connect(self.refresh_monitor)
        controls.addWidget(refresh_button)

        self.auto_refresh_checkbox = QCheckBox("Auto Refresh")
        self.auto_refresh_checkbox.toggled.connect(self._toggle_auto_refresh)
        controls.addWidget(self.auto_refresh_checkbox)

        controls.addWidget(QLabel("Interval (s):"))
        self.refresh_interval_spin = QSpinBox()
        self.refresh_interval_spin.setRange(1, 300)
        self.refresh_interval_spin.setValue(5)
        self.refresh_interval_spin.valueChanged.connect(self._refresh_timer_interval)
        controls.addWidget(self.refresh_interval_spin)
        controls.addStretch(1)
        layout.addLayout(controls)

        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.refresh_monitor)

        raw_label = QLabel("Raw --info output:")
        layout.addWidget(raw_label)
        self.monitor_raw_output = QTextEdit()
        self.monitor_raw_output.setReadOnly(True)
        self.monitor_raw_output.setMaximumHeight(140)
        layout.addWidget(self.monitor_raw_output)

        return page

    def _apply_palette_adaptation(self) -> None:
        palette = self.palette()
        window_lightness = palette.color(QPalette.ColorRole.Window).lightness()
        is_dark = window_lightness < 128

        if is_dark:
            self.output_text.setStyleSheet("QTextEdit { background: #1f232a; color: #e7e7e7; }")
            self.monitor_raw_output.setStyleSheet(
                "QTextEdit { background: #1f232a; color: #e7e7e7; }"
            )
        else:
            self.output_text.setStyleSheet("")
            self.monitor_raw_output.setStyleSheet("")

    def _load_profiles_on_startup(self) -> None:
        try:
            data = self.profile_manager.load_all()
        except ProfileError as exc:
            self._show_error(str(exc))
            data = {
                "selected": "",
                "profiles": {},
            }

        self.current_data = data
        self.set_controls_from_values(default_profile_values())
        self._reload_profile_dropdown(data["selected"])
        self._refresh_integration_checkboxes()

    def _reload_profile_dropdown(self, selected: str) -> None:
        visible_profiles = self._visible_profile_names()
        self.profile_dropdown.blockSignals(True)
        self.profile_dropdown.clear()
        for name in visible_profiles:
            self.profile_dropdown.addItem(name)
        if selected and selected in visible_profiles:
            index = self.profile_dropdown.findText(selected)
            if index >= 0:
                self.profile_dropdown.setCurrentIndex(index)
        elif visible_profiles:
            self.profile_dropdown.setCurrentIndex(0)
        else:
            self.profile_dropdown.setEditText("")
        self.profile_dropdown.blockSignals(False)
        self._update_profile_action_state()
        if self.profile_dropdown.currentText():
            self.on_profile_selected(self.profile_dropdown.currentText())

    def on_profile_selected(self, profile_name: str) -> None:
        profile_name = profile_name.strip()
        if not profile_name:
            self._update_profile_action_state()
            return
        if self._is_read_only_profile(profile_name):
            self._update_status(
                "Initial Default is hidden from selection and only used by Reset to Default",
                False,
            )
            self.profile_dropdown.blockSignals(True)
            self.profile_dropdown.setEditText("")
            self.profile_dropdown.blockSignals(False)
            self._update_profile_action_state()
            return
        values = self.current_data["profiles"].get(profile_name)
        if not values:
            self._update_profile_action_state()
            return
        self.set_controls_from_values(values)
        self.current_data["selected"] = profile_name
        self.profile_manager.save_all(self.current_data)
        self._update_profile_action_state()
        self._update_status(f"Loaded profile: {profile_name}", True)

    def collect_current_values(self) -> dict:
        values = {}
        for key, control in self.option_controls.items():
            values[key] = control.value()
            values[f"{key}_enabled"] = control.is_enabled()
        for key, control in self.boolean_controls.items():
            values[key] = control.isChecked()
        return values

    def set_controls_from_values(self, values: dict) -> None:
        defaults = default_profile_values()
        merged = {**defaults, **values}

        for key, control in self.option_controls.items():
            control.set_value(int(merged.get(key, defaults[key])))
            control.set_option_enabled(bool(merged.get(f"{key}_enabled", False)))
        for key, checkbox in self.boolean_controls.items():
            checkbox.setChecked(bool(merged.get(key, defaults[key])))

    def save_current_profile(self) -> None:
        name = self.profile_dropdown.currentText().strip()
        if not name:
            self._show_error("Please type a profile name.")
            return
        if self._is_read_only_profile(name):
            self._show_error("Reserved name. Initial Default is internal and read-only.")
            return
        values = self.collect_current_values()
        try:
            self.current_data = self.profile_manager.upsert_profile(name, values)
            self._reload_profile_dropdown(name)
            self._update_status(f"Profile saved: {name}", True)
        except ProfileError as exc:
            self._show_error(str(exc))

    def delete_selected_profile(self) -> None:
        name = self.profile_dropdown.currentText().strip()
        if not name:
            return
        if self._is_read_only_profile(name):
            self._show_error("This profile is read-only and cannot be deleted.")
            return
        was_selected_profile = name == self.current_data.get("selected", "")

        answer = QMessageBox.question(
            self,
            "Delete Profile",
            f"Delete profile '{name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        try:
            self.current_data = self.profile_manager.delete_profile(name)
            self._reload_profile_dropdown(self.current_data["selected"])
            if not self._visible_profile_names():
                self.set_controls_from_values(default_profile_values())
            if was_selected_profile and (
                self._is_boot_integration_enabled() or self._is_resume_integration_enabled()
            ):
                self._remove_profile_bound_integrations()
            self._update_status(f"Deleted profile: {name}", True)
        except ProfileError as exc:
            self._show_error(str(exc))

    def reset_to_defaults(self) -> None:
        values = self.current_data.get("profiles", {}).get(self.INITIAL_DEFAULT_PROFILE_NAME)
        if not values:
            self._update_status("Initial Default profile not set yet", False)
            return
        self.set_controls_from_values(values)
        self.current_data["selected"] = ""
        self.profile_manager.save_all(self.current_data)
        self.profile_dropdown.blockSignals(True)
        self.profile_dropdown.setEditText("")
        self.profile_dropdown.blockSignals(False)
        self._update_profile_action_state()
        self._update_status(
            "Initial defaults loaded. Press Apply to activate these values.",
            True,
        )

    def import_profiles(self) -> None:
        path_text, _ = QFileDialog.getOpenFileName(
            self,
            "Import Profiles",
            str(Path.home()),
            "JSON Files (*.json)",
        )
        if not path_text:
            return

        try:
            self.current_data = self.profile_manager.import_profiles(Path(path_text))
            self._reload_profile_dropdown(self.current_data["selected"])
            self._update_status(f"Imported profiles from {path_text}", True)
        except ProfileError as exc:
            self._show_error(str(exc))

    def export_profiles(self) -> None:
        path_text, _ = QFileDialog.getSaveFileName(
            self,
            "Export Profiles",
            str(Path.home() / "ryzenadj-profiles.json"),
            "JSON Files (*.json)",
        )
        if not path_text:
            return

        try:
            self.profile_manager.export_profiles(Path(path_text))
            self._update_status(f"Exported profiles to {path_text}", True)
        except ProfileError as exc:
            self._show_error(str(exc))

    def apply_current_values(self) -> None:
        values = self.collect_current_values()
        command = build_ryzenadj_command(values)
        if len(command) == 1:
            self._update_status("No active settings selected for Apply", False)
            self._append_output(" ".join(command), "", "No active settings selected.")
            return

        if self._should_auto_sync_after_apply():
            self._run_apply_with_active_integration_sync(values)
            return

        self.apply_button.setEnabled(False)
        self._update_status("Applying profile...", True)

        self.executor.run_async(
            command,
            use_pkexec=self.use_pkexec_checkbox.isChecked(),
            callback=self._on_apply_finished,
        )

    def _on_apply_finished(self, success: bool, stdout: str, stderr: str, command: str) -> None:
        self._append_output(command, stdout, stderr)
        if success:
            self.apply_button.setEnabled(True)
            self._update_status("Profile applied successfully", True)
        else:
            self.apply_button.setEnabled(True)
            if self._is_warning_dominated_output(stdout, stderr):
                self._update_status("Profile applied with warnings", True)
                return
            hint = ""
            if "permission denied" in stderr.lower() and not self.use_pkexec_checkbox.isChecked():
                hint = " (enable pkexec in System page)"
            self._update_status(f"Apply failed{hint}", False)

    def capture_initial_default_profile(self) -> None:
        self._update_status("Reading initial defaults from ryzenadj --info...", True)
        self.executor.run_async(
            ["ryzenadj", "--info"],
            use_pkexec=self.use_pkexec_checkbox.isChecked(),
            callback=self._on_initial_default_capture_finished,
        )

    def _on_initial_default_capture_finished(
        self,
        success: bool,
        stdout: str,
        stderr: str,
        command: str,
    ) -> None:
        self._append_output(command, stdout, stderr)
        if not success:
            self._update_status("Failed to capture initial defaults", False)
            return

        values = parse_profile_values_from_info(stdout)
        previous_visible = self.profile_dropdown.currentText().strip()
        try:
            self.current_data = self.profile_manager.upsert_profile(
                self.INITIAL_DEFAULT_PROFILE_NAME,
                values,
            )
            if previous_visible in self._visible_profile_names():
                self.current_data["selected"] = previous_visible
            else:
                self.current_data["selected"] = ""
            self.profile_manager.save_all(self.current_data)
            self._reload_profile_dropdown(self.current_data["selected"])
            self._update_status("Initial default profile captured", True)
        except ProfileError as exc:
            self._show_error(str(exc))

    def apply_system_integration(self) -> None:
        if not self.apply_boot_checkbox or not self.apply_resume_checkbox:
            return
        if not self.start_gui_on_login_checkbox:
            return

        command = build_ryzenadj_command(
            self.collect_current_values(),
            binary="/usr/bin/ryzenadj",
        )
        wants_boot = self.apply_boot_checkbox.isChecked()
        wants_resume = self.apply_resume_checkbox.isChecked()
        wants_login_autostart = self.start_gui_on_login_checkbox.isChecked()

        if (wants_boot or wants_resume) and len(command) == 1:
            self._show_error("Enable at least one setting before applying boot/resume integration.")
            return

        if len(command) == 1:
            command = ["/usr/bin/ryzenadj"]

        script = self.systemd_manager.build_sync_script(
            command=command,
            enable_boot=wants_boot,
            enable_resume=wants_resume,
        )
        self._update_status("Applying integration settings...", True)

        def _callback(success: bool, stdout: str, stderr: str, shell_command: str) -> None:
            self._on_system_integration_finished(
                success,
                stdout,
                stderr,
                shell_command,
                wants_login_autostart,
            )

        self.executor.run_shell_async(
            script,
            use_pkexec=self.use_pkexec_checkbox.isChecked(),
            callback=_callback,
        )

    def _on_system_integration_finished(
        self,
        success: bool,
        stdout: str,
        stderr: str,
        command: str,
        wants_login_autostart: bool,
    ) -> None:
        self._append_output(command, stdout, stderr)
        autostart_ok, autostart_message = self._set_gui_autostart(wants_login_autostart)
        if success and autostart_ok:
            self._update_status("Integration settings updated", True)
        elif self._is_warning_dominated_output(stdout, stderr) and autostart_ok:
            self._update_status("Integration updated with warnings", True)
        else:
            issues = []
            if not success:
                issues.append("system integration update failed")
            if not autostart_ok:
                issues.append(autostart_message)
            self._update_status("; ".join(issues), False)
        self._refresh_integration_checkboxes()

    def _should_auto_sync_after_apply(self) -> bool:
        if not self.auto_sync_integration_checkbox:
            return False
        if not self.auto_sync_integration_checkbox.isChecked():
            return False
        return self._is_boot_integration_enabled() or self._is_resume_integration_enabled()

    def _run_apply_with_active_integration_sync(self, values: dict) -> None:
        active_boot = self._is_boot_integration_enabled()
        active_resume = self._is_resume_integration_enabled()
        command_sync = build_ryzenadj_command(values, binary="/usr/bin/ryzenadj")
        if len(command_sync) == 1:
            self._update_status(
                "No active settings selected for Apply",
                False,
            )
            self._append_output("/usr/bin/ryzenadj", "", "No active settings selected.")
            return

        integration_script = self.systemd_manager.build_sync_script(
            command=command_sync,
            enable_boot=active_boot,
            enable_resume=active_resume,
        )
        apply_line = shlex.join(command_sync)
        script = "\n".join(
            [
                "set -euo pipefail",
                apply_line,
                integration_script,
            ]
        )

        self.apply_button.setEnabled(False)
        self._update_status("Applying profile and syncing active integration...", True)

        def _callback(success: bool, stdout: str, stderr: str, shell_command: str) -> None:
            self._append_output(shell_command, stdout, stderr)
            self.apply_button.setEnabled(True)
            if success:
                self._update_status("Profile applied and active integration updated", True)
            elif self._is_warning_dominated_output(stdout, stderr):
                self._update_status("Profile applied and integration updated with warnings", True)
            else:
                self._update_status("Apply or integration sync failed", False)
            self._refresh_integration_checkboxes()

        self.executor.run_shell_async(
            script,
            use_pkexec=self.use_pkexec_checkbox.isChecked(),
            callback=_callback,
        )

    def refresh_monitor(self) -> None:
        self._update_status("Refreshing ryzenadj --info...", True)
        self.executor.run_async(
            ["ryzenadj", "--info"],
            use_pkexec=self.use_pkexec_checkbox.isChecked(),
            callback=self._on_monitor_finished,
        )

    def _on_monitor_finished(self, success: bool, stdout: str, stderr: str, command: str) -> None:
        self._append_output(command, stdout, stderr)

        if not success:
            self._update_status("Monitoring refresh failed", False)
            return

        parsed = parse_info_output(stdout)
        for key, label in self.monitor_labels.items():
            label.setText(parsed.get(key, "N/A"))

        self.monitor_raw_output.setPlainText(stdout)
        self._update_status("Monitoring data refreshed", True)

    def _toggle_auto_refresh(self, checked: bool) -> None:
        if checked:
            self.refresh_timer.start(self.refresh_interval_spin.value() * 1000)
            self._update_status("Auto-refresh enabled", True)
            self.refresh_monitor()
        else:
            self.refresh_timer.stop()
            self._update_status("Auto-refresh disabled", True)

    def _refresh_timer_interval(self, seconds: int) -> None:
        if self.refresh_timer.isActive():
            self.refresh_timer.start(seconds * 1000)

    def _append_output(self, command: str, stdout: str, stderr: str) -> None:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        lines = [f"[{timestamp}] $ {command}"]
        if stdout:
            lines.append(stdout)
        if stderr:
            lines.append(stderr)
        if not stdout and not stderr:
            lines.append("(no output)")
        lines.append("")
        self.output_text.append("\n".join(lines))

    def _update_profile_action_state(self, *_: object) -> None:
        current_name = self.profile_dropdown.currentText().strip()
        has_name = bool(current_name)
        exists = current_name in self._visible_profile_names()
        readonly = self._is_read_only_profile(current_name)
        has_initial_default = (
            self.INITIAL_DEFAULT_PROFILE_NAME in self.current_data.get("profiles", {})
        )

        if self.save_button:
            self.save_button.setEnabled(has_name and not readonly)
        if self.delete_button:
            self.delete_button.setEnabled(exists and not readonly)
        if self.reset_button:
            self.reset_button.setEnabled(has_initial_default)

    def _wire_mutually_exclusive_mode_flags(self) -> None:
        power_saving = self.boolean_controls.get("power_saving")
        max_performance = self.boolean_controls.get("max_performance")
        if not power_saving or not max_performance:
            return

        def _on_power_saving_changed(checked: bool) -> None:
            if checked:
                max_performance.blockSignals(True)
                max_performance.setChecked(False)
                max_performance.blockSignals(False)

        def _on_max_performance_changed(checked: bool) -> None:
            if checked:
                power_saving.blockSignals(True)
                power_saving.setChecked(False)
                power_saving.blockSignals(False)

        power_saving.toggled.connect(_on_power_saving_changed)
        max_performance.toggled.connect(_on_max_performance_changed)

    def _is_read_only_profile(self, name: str) -> bool:
        return name.strip() == self.INITIAL_DEFAULT_PROFILE_NAME

    def _visible_profile_names(self) -> list[str]:
        return [
            name
            for name in self.current_data.get("profiles", {}).keys()
            if name != self.INITIAL_DEFAULT_PROFILE_NAME
        ]

    def _refresh_integration_checkboxes(self) -> None:
        if not self.apply_boot_checkbox or not self.apply_resume_checkbox:
            return
        if not self.start_gui_on_login_checkbox:
            return

        self.apply_boot_checkbox.blockSignals(True)
        self.apply_resume_checkbox.blockSignals(True)
        self.start_gui_on_login_checkbox.blockSignals(True)

        self.apply_boot_checkbox.setChecked(self._is_boot_integration_enabled())
        self.apply_resume_checkbox.setChecked(self._is_resume_integration_enabled())
        self.start_gui_on_login_checkbox.setChecked(self._is_gui_autostart_enabled())

        self.apply_boot_checkbox.blockSignals(False)
        self.apply_resume_checkbox.blockSignals(False)
        self.start_gui_on_login_checkbox.blockSignals(False)

    def _is_boot_integration_enabled(self) -> bool:
        try:
            proc = subprocess.run(
                ["systemctl", "is-enabled", "ryzenadj-gui.service"],
                check=False,
                capture_output=True,
                text=True,
            )
            return proc.returncode == 0 and proc.stdout.strip() == "enabled"
        except OSError:
            return False

    def _is_resume_integration_enabled(self) -> bool:
        return Path("/usr/lib/systemd/system-sleep/ryzenadj-gui-resume").exists()

    def _gui_autostart_path(self) -> Path:
        return Path.home() / ".config" / "autostart" / "ryzenadj-gui.desktop"

    def _is_gui_autostart_enabled(self) -> bool:
        return self._gui_autostart_path().exists()

    def _set_gui_autostart(self, enabled: bool) -> tuple[bool, str]:
        autostart_path = self._gui_autostart_path()
        try:
            if enabled:
                autostart_path.parent.mkdir(parents=True, exist_ok=True)
                exec_command = "ryzenadj-gui"
                if not Path("/usr/bin/ryzenadj-gui").exists():
                    main_path = (Path(__file__).resolve().parent.parent / "main.py").as_posix()
                    exec_command = f"python {main_path}"
                content = "\n".join(
                    [
                        "[Desktop Entry]",
                        "Type=Application",
                        "Name=RyzenAdj GUI",
                        "Comment=Frontend for ryzenadj",
                        f"Exec={exec_command}",
                        "Icon=utilities-system-monitor",
                        "Terminal=false",
                        "Categories=System;Settings;",
                        "StartupNotify=true",
                        "",
                    ]
                )
                autostart_path.write_text(content, encoding="utf-8")
            else:
                autostart_path.unlink(missing_ok=True)
            return True, ""
        except OSError as exc:
            return False, f"GUI autostart update failed: {exc}"

    def _remove_profile_bound_integrations(self) -> None:
        script = self.systemd_manager.build_sync_script(
            command=["/usr/bin/ryzenadj"],
            enable_boot=False,
            enable_resume=False,
        )

        def _callback(success: bool, stdout: str, stderr: str, shell_command: str) -> None:
            self._append_output(shell_command, stdout, stderr)
            if success:
                self._update_status(
                    "Deleted active profile and removed boot/resume integration",
                    True,
                )
            else:
                self._update_status(
                    "Profile deleted, but removing boot/resume integration failed",
                    False,
                )
            self._refresh_integration_checkboxes()

        self.executor.run_shell_async(
            script,
            use_pkexec=self.use_pkexec_checkbox.isChecked(),
            callback=_callback,
        )

    def _is_warning_dominated_output(self, stdout: str, stderr: str) -> bool:
        text = "\n".join([stdout or "", stderr or ""]).strip().lower()
        if not text:
            return False

        has_warning = any(pattern in text for pattern in self.WARNING_PATTERNS)
        if not has_warning:
            return False

        has_fatal = any(pattern in text for pattern in self.FATAL_PATTERNS)
        return not has_fatal

    def _update_status(self, text: str, success: bool) -> None:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        state = "SUCCESS" if success else "ERROR"
        self.status_text.setText(f"{state}: {text}")
        self.status_timestamp.setText(timestamp)

    def _show_error(self, message: str) -> None:
        self._update_status(message, False)
        QMessageBox.critical(self, "Error", message)
