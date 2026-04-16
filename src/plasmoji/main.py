"""
Plasmoji — entry point.

Sets up logging, the Qt application, the D-Bus service, the QML↔Python
bridge, and loads the QML UI.  Designed to run as a long-lived background
daemon (``QuitOnLastWindowClosed`` is disabled).
"""

import logging
import os
import sys
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

from plasmoji import __app_id__, __version__
from plasmoji.bridge import WindowBridge
from plasmoji.controller import PlasmojiController
from plasmoji.dbus_service import PlasmojiDBusService

logger = logging.getLogger("plasmoji")

# Resolve paths relative to *this* file so it works from any cwd.
_SRC_DIR = Path(__file__).resolve().parent          # src/plasmoji/
_PROJECT_ROOT = _SRC_DIR.parent.parent              # plasmoji/
_QML_DIR = _PROJECT_ROOT / "qml"


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        datefmt="%H:%M:%S",
    )


def main() -> int:
    # ── Wayland constraint ──────────────────────────────────────────
    os.environ["QT_QPA_PLATFORM"] = "wayland"

    _configure_logging()
    logger.info("Plasmoji v%s starting…", __version__)

    # ── Qt Application ──────────────────────────────────────────────
    app = QGuiApplication(sys.argv)
    app.setApplicationName("Plasmoji")
    app.setApplicationVersion(__version__)
    app.setDesktopFileName(__app_id__)
    app.setOrganizationDomain("ashutoshtiwari.dev")
    app.setQuitOnLastWindowClosed(False)  # daemon mode

    # ── QML ↔ Python bridge ─────────────────────────────────────────
    bridge = WindowBridge()

    # ── D-Bus service ───────────────────────────────────────────────
    dbus_service = PlasmojiDBusService()
    if not dbus_service.register():
        logger.critical("D-Bus registration failed — aborting.")
        return 1

    # Wire DBus → Bridge
    dbus_service.visibility_toggle_requested.connect(bridge.toggle)

    # ── Controller ──────────────────────────────────────────────────
    controller = PlasmojiController()
    
    # ── QML engine ──────────────────────────────────────────────────
    engine = QQmlApplicationEngine()

    # Expose the bridge and controller to QML
    engine.rootContext().setContextProperty("windowBridge", bridge)
    engine.rootContext().setContextProperty("controller", controller)

    qml_entry = _QML_DIR / "main.qml"
    if not qml_entry.exists():
        logger.critical("QML entry point not found: %s", qml_entry)
        return 1

    engine.load(QUrl.fromLocalFile(str(qml_entry)))

    if not engine.rootObjects():
        logger.critical("QML failed to load — no root objects created.")
        return 1

    logger.info(
        "Plasmoji daemon ready.  "
        "Call ToggleVisibility via: "
        "busctl --user call %s %s dev.ashutoshtiwari.plasmoji.PlasmojiDBusService ToggleVisibility",
        __app_id__,
        "/" + __app_id__.replace(".", "/"),
    )

    # ── Event loop ──────────────────────────────────────────────────
    exit_code = app.exec()

    # Cleanup
    dbus_service.unregister()
    logger.info("Plasmoji shut down (exit code %d)", exit_code)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
