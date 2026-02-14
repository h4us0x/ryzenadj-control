"""Application entry point for ryzenadj-gui."""

import sys
from pathlib import Path

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication

from ui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("ryzenadj-gui")
    app.setOrganizationName("ryzenadj-gui")
    icons_dir = Path(__file__).resolve().parent / "resources" / "icons"
    taskbar_icon_path = icons_dir / "logo-taskbar.svg"
    window_icon_png_path = icons_dir / "logo-window.png"

    if taskbar_icon_path.exists():
        app.setWindowIcon(QIcon(str(taskbar_icon_path)))

    window = MainWindow()
    if window_icon_png_path.exists():
        window.setWindowIcon(QIcon(str(window_icon_png_path)))
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
