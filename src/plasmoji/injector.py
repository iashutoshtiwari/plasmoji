"""
Wayland Injector for Plasmoji.

Provides the `WaylandInjector` class which circumvents Wayland's strict client
isolation by orchestrating `wl-clipboard` and `wtype`.
"""

import logging
import subprocess
import time

logger = logging.getLogger(__name__)


class WaylandInjector:
    """
    Handles keystroke injection and clipboard management on Wayland.

    To safely inject content:
    1. Reads and stores current clipboard.
    2. Overwrites clipboard with new asset (supports MIME types).
    3. Simulates 'Ctrl+V' via wtype.
    4. Restores original clipboard contents.
    """

    def __init__(self) -> None:
        pass

    def _get_current_clipboard(self, mime_type: str = "text/plain") -> bytes | None:
        """
        Fetch the current clipboard content for a given MIME type.
        """
        try:
            # We use `wl-paste` to extract the clipboard.
            # Using --no-newline to prevent trailing newlines for text.
            result = subprocess.run(
                ["wl-paste", "--type", mime_type, "--no-newline"],
                capture_output=True,
                check=True
            )
            return result.stdout
        except FileNotFoundError:
            logger.error("wl-paste not found. Is wl-clipboard installed?")
            return None
        except subprocess.CalledProcessError as e:
            # It's normal for wl-paste to fail if the clipboard is empty for the requested type.
            logger.debug("Clipboard empty or format not available. (%s)", e)
            return None
        except Exception as e:
            logger.error("Unexpected error reading clipboard: %s", e)
            return None

    def _set_clipboard(self, data: bytes, mime_type: str = "text/plain") -> bool:
        """
        Write data into the clipboard using `wl-copy`.
        """
        try:
            subprocess.run(
                ["wl-copy", "--type", mime_type],
                input=data,
                check=True
            )
            return True
        except FileNotFoundError:
            logger.error("wl-copy not found. Is wl-clipboard installed?")
            return False
        except subprocess.CalledProcessError as e:
            logger.error("wl-copy failed: %s", e)
            return False
        except Exception as e:
            logger.error("Unexpected error writing to clipboard: %s", e)
            return False

    def _clear_clipboard(self) -> None:
        """Clear the clipboard if it was initially empty."""
        try:
            subprocess.run(["wl-copy", "--clear"], check=True)
        except OSError as e:
            logger.error("Failed to clear clipboard: %s", e)

    def _trigger_paste(self) -> bool:
        """
        Use `wtype` to simulate `Ctrl+V`.
        """
        try:
            # wtype -M ctrl -k v -m ctrl
            subprocess.run(
                ["wtype", "-M", "ctrl", "-k", "v", "-m", "ctrl"],
                check=True
            )
            return True
        except FileNotFoundError:
            logger.error("wtype not found. Please install wtype.")
            return False
        except subprocess.CalledProcessError as e:
            logger.error("wtype injection failed: %s", e)
            return False
        except Exception as e:
            logger.error("Unexpected error during wtype injection: %s", e)
            return False

    def inject(self, asset: str | bytes, mime_type: str = "text/plain") -> bool:
        """
        Safely injects the given asset into the active window.

        Args:
            asset: The content to inject. Can be text (str) or raw file bytes (bytes) for GIFs.
            mime_type: The MIME type of the payload (e.g., 'text/plain', 'image/gif').

        Returns:
            True if the injection sequence completed successfully, False otherwise.
        """
        logger.info("Starting injection pipeline for %s...", mime_type)

        # Ensure asset is bytes for subprocess pipes
        if isinstance(asset, str):
            asset_bytes = asset.encode("utf-8")
        else:
            asset_bytes = asset

        # 1. Read & Store
        original_clipboard = self._get_current_clipboard(mime_type=mime_type)

        # 2. Stage
        if not self._set_clipboard(asset_bytes, mime_type=mime_type):
            logger.error("Aborting injection: Staging failed.")
            return False

        # Micro-delay to allow compositor clipboard synchronization before keystroke
        time.sleep(0.05)

        # 3. Inject
        if not self._trigger_paste():
            logger.error("Injection failed at wtype simulation stage.")
            # Even if injection failed, we should still try to restore clipboard data.

        # Another micro-delay to let the target app process the Paste action before we yank the clipboard away.
        time.sleep(0.05)

        # 4. Restore
        if original_clipboard is not None:
            self._set_clipboard(original_clipboard, mime_type=mime_type)
        else:
            self._clear_clipboard()

        logger.info("Injection pipeline completed successfully.")
        return True
