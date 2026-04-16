"""
QML ↔ Python bridge for window state management.

Exposes properties and slots that the QML UI binds to.
The DBus service triggers ``toggle()`` which flips the visibility state.
"""

from PySide6.QtCore import Property, QObject, Signal, Slot


class WindowBridge(QObject):
    """
    Lightweight bridge that tracks window visibility and is exposed
    to QML as a context property (``windowBridge``).

    Properties:
        windowVisible (bool): Whether the Plasmoji window should be shown.
    """

    visibilityChanged = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._visible: bool = False

    # ------------------------------------------------------------------
    # Properties (read by QML)
    # ------------------------------------------------------------------

    @Property(bool, notify=visibilityChanged)
    def windowVisible(self) -> bool:  # noqa: N802
        return self._visible

    # ------------------------------------------------------------------
    # Slots (callable from QML and Python)
    # ------------------------------------------------------------------

    @Slot()
    def toggle(self) -> None:
        """Toggle window visibility."""
        self._visible = not self._visible
        self.visibilityChanged.emit()

    @Slot()
    def dismiss(self) -> None:
        """Hide the window (e.g. on Escape or focus loss)."""
        if self._visible:
            self._visible = False
            self.visibilityChanged.emit()

    @Slot()
    def show(self) -> None:
        """Explicitly show the window."""
        if not self._visible:
            self._visible = True
            self.visibilityChanged.emit()
