"""
Network layer for fetching and securely caching GIFs via the KLIPY API.
"""

import configparser
import json
import logging
import urllib.parse
import urllib.request
from pathlib import Path
from urllib.error import URLError

logger = logging.getLogger(__name__)


class KlipyClient:
    """
    Downloads and caches GIFs locally using the Klipy API.
    """

    API_BASE = "https://api.klipy.co/v1"

    def __init__(self) -> None:
        self._enabled = False
        self._api_key = ""
        self._cache_dir = Path.home() / ".cache" / "plasmoji" / "gifs"

        self._init_config()
        if self._enabled:
            self._cache_dir.mkdir(parents=True, exist_ok=True)

    def _init_config(self) -> None:
        """Reads the configuration for the API key."""
        config_path = Path.home() / ".config" / "plasmoji" / "config.ini"
        if not config_path.exists():
            logger.warning("No config.ini found at %s. GIF features disabled.", config_path)
            return

        try:
            config = configparser.ConfigParser()
            config.read(config_path)
            if "Klipy" in config and "ApiKey" in config["Klipy"]:
                self._api_key = config["Klipy"]["ApiKey"].strip()
                if self._api_key:
                    self._enabled = True
                    logger.info("Klipy GIF integration fully enabled.")
                else:
                    logger.warning("Empty Klipy ApiKey. GIF features disabled.")
            else:
                logger.warning("config.ini missing [Klipy] section with ApiKey.")
        except Exception as e:
            logger.error("Failed to parse config.ini: %s", e)

    @property
    def is_enabled(self) -> bool:
        return self._enabled

    def _make_request(self, endpoint: str, query_params: dict | None = None) -> list[dict]:
        """Core Request builder handling Auth and JSON parsing."""
        if not self._enabled:
            return []

        url = f"{self.API_BASE}/{endpoint}"
        if query_params:
            url = f"{url}?{urllib.parse.urlencode(query_params)}"

        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {self._api_key}"})

        try:
            with urllib.request.urlopen(req, timeout=5.0) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode("utf-8"))
                    # Note: We parse Klipy structure. Let's assume an array under 'data'
                    # which is standard for modern media APIs.
                    return data.get("data", [])
                else:
                    logger.warning("Klipy API returned HTTP %d", response.status)
        except URLError as e:
            logger.error("Network error reaching Klipy API: %s", e)
        except Exception as e:
            logger.error("Unexpected error parsing Klipy API response: %s", e)

        return []

    def get_trending(self, limit: int = 20) -> list[dict]:
        """Fetch current trending GIFs."""
        return self._make_request("gifs/trending", {"limit": limit})

    def search_gifs(self, query: str, limit: int = 20) -> list[dict]:
        """Fuzzy search the GIF database."""
        if not query.strip():
            return self.get_trending(limit=limit)
        return self._make_request("gifs/search", {"q": query, "limit": limit})

    def fetch_and_cache_gif(self, asset_id: str, fetch_url: str) -> Path | None:
        """
        Downloads a target GIF strictly into the cache directory.
        If it exists in the cache, returns the local path immediately.
        """
        if not self._enabled:
            return None

        # Sanitize filename
        safe_id = "".join(c for c in asset_id if c.isalnum() or c in ('-', '_'))
        file_path = self._cache_dir / f"{safe_id}.gif"

        # Check Cache
        if file_path.exists():
            return file_path

        # Network Download
        logger.debug("Network cache miss. Downloading GIF %s", safe_id)
        try:
            req = urllib.request.Request(fetch_url)
            with urllib.request.urlopen(req, timeout=10.0) as response:
                if response.status == 200:
                    file_path.write_bytes(response.read())
                    return file_path
        except Exception as e:
            logger.error("Failed to download and cache GIF %s: %s", asset_id, e)

        return None
