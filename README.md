# Plasmoji

> Emoji, Kaomoji & GIF selector for KDE Plasma 6 on Wayland.

Plasmoji is a lightweight, daemon-based picker inspired by the Windows 11
emoji panel.  It runs as a background service with zero-latency D-Bus
activation and injects selected assets directly into the focused window
via `wl-copy` / `wtype`.

## Requirements

| Dependency    | Purpose                        |
|---------------|--------------------------------|
| Python ≥ 3.11 | Runtime                        |
| PySide6 ≥ 6.6 | Qt 6 / QML / QtDBus bindings   |
| wl-clipboard  | Wayland clipboard access       |
| wtype         | Wayland keystroke simulation   |

## Quick Start

```bash
# Install in editable mode
pip install -e .

# Run the daemon
python -m plasmoji.main
```

## Toggle the Window

Once the daemon is running, call `ToggleVisibility` over D-Bus:

```bash
busctl --user call \
  dev.ashutoshtiwari.Plasmoji \
  /dev/ashutoshtiwari/Plasmoji \
  dev.ashutoshtiwari.plasmoji.PlasmojiDBusService \
  ToggleVisibility
```

Or with `dbus-send`:

```bash
dbus-send --session --type=method_call \
  --dest=dev.ashutoshtiwari.Plasmoji \
  /dev/ashutoshtiwari/Plasmoji \
  dev.ashutoshtiwari.plasmoji.PlasmojiDBusService.ToggleVisibility
```

Bind either command to a global keyboard shortcut in KDE System Settings
for instant access.

## Project Structure

```
plasmoji/
├── src/plasmoji/
│   ├── __init__.py        # Package metadata
│   ├── main.py            # Entry point & QGuiApplication setup
│   ├── dbus_service.py    # D-Bus session service (QtDBus)
│   └── bridge.py          # QML ↔ Python state bridge
├── qml/
│   └── main.qml           # UI (placeholder in Phase 1)
├── assets/                # Icons, images (future)
├── data/                  # SQLite emoji database (future)
└── pyproject.toml
```

## License

MIT
