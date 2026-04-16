"""
Controller module bridging the QML UI, Wayland Injector, and SQLite Database.
"""

import configparser
import logging
from pathlib import Path

from PySide6.QtCore import Property, QObject, QRunnable, QThreadPool, Signal, Slot
from PySide6.QtGui import QColor

from plasmoji.database import DataStore
from plasmoji.injector import WaylandInjector
from plasmoji.network import KlipyClient

logger = logging.getLogger(__name__)


class SearchTask(QRunnable):
    """Background task to query SQLite without blocking the QML thread."""

    def __init__(self, query: str, data_store: DataStore, callback):
        super().__init__()
        self.query = query
        self.data_store = data_store
        self.callback = callback

    def run(self):
        try:
            results = self.data_store.search(self.query)
            
            # Map dataclass to dict for QML QVariantList consumption
            qml_results = []
            for r in results:
                qml_results.append({
                    "id": r.id,
                    "type": r.asset_type,
                    "asset_string": r.asset_string,
                    "keywords": r.keywords
                })
            
            self.callback(self.query, qml_results)
        except Exception as e:
            logger.error("SearchTask failed: %s", e)
            self.callback(self.query, [])


class GifSearchTask(QRunnable):
    """Background task to query the Klipy Network without blocking the QML thread."""

    def __init__(self, query: str, network_client: KlipyClient, callback):
        super().__init__()
        self.query = query
        self.network_client = network_client
        self.callback = callback

    def run(self):
        try:
            results = self.network_client.search_gifs(self.query)
            
            # Format results for QML consumption
            qml_results = []
            for r in results:
                qml_results.append({
                    "id": r.get("id"),
                    "type": "gif",
                    "asset_string": r.get("url", ""), # Placeholder URL for grid thumbnails
                    "keywords": self.query,
                    "download_url": r.get("media_url", "") # Hypothetical property
                })
            
            self.callback(self.query, qml_results)
        except Exception as e:
            logger.error("GifSearchTask failed: %s", e)
            self.callback(self.query, [])


class PlasmojiController(QObject):
    """
    Main bridging controller.
    Provides methods to QML for interacting with the backend layers.
    """

    # Signal emitted when a background search completes
    searchResultsReady = Signal(str, "QVariantList")
    gifSearchResultsReady = Signal(str, "QVariantList")
    
    # Signal emitted when an injection triggers, used to hide window
    injectionRequested = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._data_store = DataStore()
        self._data_store.connect()
        self._injector = WaylandInjector()
        self._klipy_client = KlipyClient()
        self._thread_pool = QThreadPool.globalInstance()

    @Slot(str)
    def search(self, query: str) -> None:
        """
        Asynchronously searches the database.
        Results are emitted via searchResultsReady signal.
        """
        task = SearchTask(query, self._data_store, self._on_search_completed)
        self._thread_pool.start(task)

    def _on_search_completed(self, query: str, results: list[dict]) -> None:
        """Callback from SearchTask run in a separate thread."""
        self.searchResultsReady.emit(query, results)

    @Slot(str)
    def search_gifs(self, query: str) -> None:
        """Asynchronously searches the Klipy network."""
        if not self._klipy_client.is_enabled:
            self.gifSearchResultsReady.emit(query, [])
            return
            
        task = GifSearchTask(query, self._klipy_client, self._on_gif_search_completed)
        self._thread_pool.start(task)

    def _on_gif_search_completed(self, query: str, results: list[dict]) -> None:
        """Callback from GifSearchTask run in a separate thread."""
        self.gifSearchResultsReady.emit(query, results)

    @Slot(str, str, str)
    def select_asset(self, asset_string: str, asset_id: str, asset_type: str) -> None:
        """
        Invoked from QML when an asset is clicked/selected.
        """
        logger.info("Asset selected: id=%s, type=%s", asset_id, asset_type)
        
        # 1. Update MRU cache (if integer/SQLite local asset)
        try:
            numeric_id = int(asset_id)
            self._data_store.record_usage(numeric_id)
        except ValueError:
            pass # Network GIFs use string UUIDs, skip basic MRU for now
        
        # 2. Hide the Plasmoji UI immediately so the focus returns to the underlying target
        self.injectionRequested.emit()
        
        # 3. Inject payload
        if asset_type == "gif":
            # For phase 5, if it's a GIF, asset_string carries the download url
            file_path = self._klipy_client.fetch_and_cache_gif(asset_id, asset_string)
            if file_path and file_path.exists():
                # Inject absolute file path to Wayland injector (some Wayland apps accept file:// links)
                # Or inject raw bytes if injector supports it
                # Injecting raw bytes by passing them in
                logger.info("Injecting cached GIF local bytes.")
                self._injector.inject(file_path.read_bytes(), mime_type="image/gif")
            else:
                logger.error("Failed to inject GIF: Cache fetch aborted.")
        else:
            self._injector.inject(asset_string, mime_type="text/plain")

    @Slot(result=str)
    def get_kdeglobals_accent(self) -> str:
        """
        Reads ~/.config/kdeglobals to fetch the active accent color.
        Returns a hex color code. Falls back to a default if failing.
        """
        default_color = "#89b4fa"  # Catppuccin Mocha Blue fallback
        
        config_path = Path.home() / ".config" / "kdeglobals"
        if not config_path.exists():
            return default_color
            
        try:
            config = configparser.ConfigParser()
            # KDE globals technically sometimes lacks a top-level section, strict=False helps
            config.read(config_path)
            
            if "General" in config and "AccentColor" in config["General"]:
                rgb_str = config["General"]["AccentColor"]
                # Convert 'R,G,B' to hex
                r, g, b = [int(p.strip()) for p in rgb_str.split(",")]
                return QColor(r, g, b).name()
                
        except Exception as e:
            logger.debug("Failed to parse kdeglobals accent color: %s", e)
            
        return default_color
