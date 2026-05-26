#!/bin/bash
# RaaS Monitor — One-command install
# Usage: curl -sL https://raw.githubusercontent.com/mcyong1973-create/raas/main/install.sh | bash

set -e

REPO="https://raw.githubusercontent.com/aion/raas/main"
VERSION="0.1.0"

echo ""
echo "  ┌─────────────────────────────────────────────┐"
echo "  │  RaaS Monitor v${VERSION} Installation             │"
echo "  │  Reputation as a Service                    │"
echo "  └─────────────────────────────────────────────┘"
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "  ✗ Python 3 is required. Install it first."
    echo "    Install with: sudo apt install python3 python3-pip"
    exit 1
fi
echo "  ✓ Python 3 found: $(python3 --version)"

# Determine install method
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOCAL_SOURCE=""
if [ -f "$SCRIPT_DIR/monitor.py" ]; then
    LOCAL_SOURCE="$SCRIPT_DIR"
elif [ -f "./monitor.py" ]; then
    LOCAL_SOURCE="$(pwd)"
fi

install_script() {
    local name="$1"
    local src="$2"
    local dst="/usr/local/bin/$name"
    
    if [ -n "$LOCAL_SOURCE" ] && [ -f "$LOCAL_SOURCE/$src" ]; then
        sudo cp "$LOCAL_SOURCE/$src" "$dst"
        echo "  ✓ $name installed from local source"
    else
        echo "  Downloading $name..."
        sudo curl -sL -o "$dst" "$REPO/$src" || {
            echo "  ✗ Download failed for $name"
            echo "    Check your internet connection or download manually from:"
            echo "    $REPO/$src"
            return 1
        }
        echo "  ✓ $name downloaded from raas.aion.io"
    fi
    sudo chmod +x "$dst"
}

# Install all components
install_script "raas-monitor" "monitor.py"
install_script "raas-dashboard" "dashboard.py"

# Save version info for future updates
echo "{\"version\":\"$VERSION\",\"repo\":\"$REPO\",\"installed\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"}" | sudo tee /usr/local/bin/.raas-version.json > /dev/null

# Initialize config if needed
if [ ! -f "$HOME/.raas/config.json" ]; then
    echo ""
    echo "  Running first-time setup..."
    raas-monitor init 2>/dev/null || true
fi

echo ""
echo "  ┌─────────────────────────────────────────────┐"
echo "  │  Installation complete!                     │"
echo "  │                                             │"
echo "  │  Commands:                                  │"
echo "  │    raas-monitor        agent tracking       │"
echo "  │    raas-dashboard      live dashboard       │"
echo "  │    raas-monitor update check for updates    │"
echo "  │                                             │"
echo "  │  Start tracking:                            │"
echo "  │    raas-monitor run my-agent -- <command>    │"
echo "  │                                             │"
echo "  │  Dashboard:                                 │"
echo "  │    raas-dashboard        (TUI)              │"
echo "  │    raas-dashboard --cli  (terminal)          │"
echo "  └─────────────────────────────────────────────┘"
echo ""
