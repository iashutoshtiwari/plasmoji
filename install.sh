#!/usr/bin/env bash
set -euo pipefail

echo "=================================================="
echo "🚀 Plasmoji Universal Installer"
echo "=================================================="
echo ""

# 1. Dependency Checks
echo "[1/4] Checking dependencies..."
MISSING_DEPS=0

for cmd in python3 wl-copy wtype; do
    if ! command -v "$cmd" &> /dev/null; then
        echo "❌ Missing dependency: $cmd"
        MISSING_DEPS=1
    fi
done

if [ "$MISSING_DEPS" -eq 1 ]; then
    echo ""
    echo "Please install the missing dependencies via your package manager."
    echo "  Arch: sudo pacman -S python wl-clipboard wtype"
    echo "  Fedora: sudo dnf install python3 wl-clipboard wtype"
    echo "  Ubuntu/Debian: sudo apt install python3 wl-clipboard wtype"
    exit 1
fi
echo "✅ All system dependencies found."

# 2. XDG Paths Setup
XDG_DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
XDG_CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}"
XDG_BIN_HOME="$HOME/.local/bin"

PLASMOJI_DIR="$XDG_DATA_HOME/plasmoji"
VENV_DIR="$PLASMOJI_DIR/venv"
SYSTEMD_DIR="$XDG_CONFIG_HOME/systemd/user"

mkdir -p "$PLASMOJI_DIR"
mkdir -p "$XDG_BIN_HOME"
mkdir -p "$SYSTEMD_DIR"

# 3. Fetching / Copying Files
echo "[2/4] Setting up project files..."
if [ -d ".git" ] && [ -f "pyproject.toml" ]; then
    echo "-> Running from local repository tree. Copying files..."
    # We copy the source so changes in repo don't break on a whim, or user can delete repo.
    # We'll sync src, assets, qml and pyproject.toml
    cp -r src assets qml pyproject.toml "$PLASMOJI_DIR/"
else
    echo "-> Cloning latest from Git..."
    if [ -d "$PLASMOJI_DIR/src" ]; then
        rm -rf "${PLASMOJI_DIR:?}"/*
    fi
    git clone https://github.com/ashutoshtiwari/plasmoji.git "$PLASMOJI_DIR"
fi

# 4. Virtual Environment & Python deps
echo "[3/4] Creating Virtual Environment & installing PySide6..."
cd "$PLASMOJI_DIR"
python3 -m venv "$VENV_DIR"
if ! "$VENV_DIR/bin/pip" install -e . ; then
    echo "❌ Failed to install Python dependencies."
    exit 1
fi

# Create global executable symlink
cat > "$XDG_BIN_HOME/plasmoji" << 'EOF'
#!/usr/bin/env bash
# Plasmoji runner
exec "$HOME/.local/share/plasmoji/venv/bin/python" -m plasmoji "$@"
EOF
chmod +x "$XDG_BIN_HOME/plasmoji"

# 5. Systemd Daemon
echo "[4/4] Installing and enabling systemd user daemon..."
cp "assets/plasmoji.service" "$SYSTEMD_DIR/"

# Update the ExecStart path to point to our venv wrapper gracefully
sed -i "s|ExecStart=.*|ExecStart=$XDG_BIN_HOME/plasmoji|" "$SYSTEMD_DIR/plasmoji.service"

systemctl --user daemon-reload
systemctl --user enable --now plasmoji.service

echo ""
echo "=================================================="
echo "✨ Plasmoji installed and running!"
echo "=================================================="
echo ""
echo "Make sure $XDG_BIN_HOME is in your \$PATH."
echo "You can trigger the UI by mapping a global KDE shortcut to:"
echo ""
echo "  busctl --user call dev.ashutoshtiwari.Plasmoji \\"
echo "    /dev/ashutoshtiwari/Plasmoji \\"
echo "    dev.ashutoshtiwari.plasmoji.PlasmojiDBusService \\"
echo "    ToggleVisibility"
echo ""
