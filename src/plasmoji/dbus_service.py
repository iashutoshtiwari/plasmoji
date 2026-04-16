"""
DBus session service for Plasmoji.

Registers `dev.ashutoshtiwari.Plasmoji` on the session bus and exposes
a `ToggleVisibility()` method directly.

Calling convention (busctl):
    busctl --user call dev.ashutoshtiwari.Plasmoji \
        /dev/ashutoshtiwari/Plasmoji \
        dev.ashutoshtiwari.plasmoji.PlasmojiDBusService \
        ToggleVisibility

Calling convention (dbus-send):
    dbus-send --session --type=method_call \
        --dest=dev.ashutoshtiwari.Plasmoji \
        /dev/ashutoshtiwari/Plasmoji \
        dev.ashutoshtiwari.plasmoji.PlasmojiDBusService.ToggleVisibility
"""

import logging

from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtDBus import QDBusConnection

from plasmoji import __app_id__

logger = logging.getLogger(__name__)

SERVICE_NAME = __app_id__
OBJECT_PATH = "/" + __app_id__.replace(".", "/")


class PlasmojiDBusService(QObject):
    """
    Root D-Bus object that owns the bus name and exposes the ToggleVisibility slot.
    The interface name exposed by PySide6 for ExportAllSlots will be local.PlasmojiDBusService by default.

    Signals:
        visibility_toggle_requested: Emitted when ToggleVisibility is called.
    """

    visibility_toggle_requested = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._registered = False

    @Slot()
    def ToggleVisibility(self) -> None:  # noqa: N802
        """Toggle Plasmoji window visibility (D-Bus exposed)."""
        logger.debug("ToggleVisibility invoked over D-Bus")
        self.visibility_toggle_requested.emit()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def is_registered(self) -> bool:
        return self._registered

    def register(self) -> bool:
        """
        Attempt to register the service on the session bus.

        Returns ``True`` on success.  Logs detailed errors on failure.
        """
        bus = QDBusConnection.sessionBus()

        if not bus.isConnected():
            logger.critical(
                "Cannot connect to D-Bus session bus. "
                "Is a session bus daemon running?"
            )
            return False

        if not bus.registerService(SERVICE_NAME):
            logger.critical(
                "Failed to own bus name '%s'. "
                "Another Plasmoji instance is probably already running. "
                "(last D-Bus error: %s)",
                SERVICE_NAME,
                bus.lastError().message(),
            )
            return False

        # Expose all slots on this object directly
        if not bus.registerObject(
            OBJECT_PATH,
            self,
            QDBusConnection.RegisterOption.ExportAllSlots,
        ):
            logger.critical(
                "Failed to register object at '%s'. (last D-Bus error: %s)",
                OBJECT_PATH,
                bus.lastError().message(),
            )
            return False

        self._registered = True
        logger.info(
            "D-Bus service active  name=%s  path=%s", SERVICE_NAME, OBJECT_PATH
        )
        return True

    def unregister(self) -> None:
        """Release the bus name (called on shutdown)."""
        if not self._registered:
            return
        bus = QDBusConnection.sessionBus()
        bus.unregisterObject(OBJECT_PATH)
        bus.unregisterService(SERVICE_NAME)
        self._registered = False
        logger.info("D-Bus service released")

