#!/usr/bin/env bash
# VPN Launcher Pro — installer
set -e

# ── Colours ────────────────────────────────────────────────────────────────
G='\033[0;32m'; B='\033[1;34m'; R='\033[0;31m'; N='\033[0m'
info()  { echo -e "${B}[*]${N} $*"; }
ok()    { echo -e "${G}[+]${N} $*"; }
err()   { echo -e "${R}[!]${N} $*"; exit 1; }

# ── Prereq check ──────────────────────────────────────────────────────────
for cmd in python3 openvpn pkexec wg-quick ip; do
    command -v "$cmd" &>/dev/null || err "missing dependency: $cmd"
done
python3 -c "import tkinter" 2>/dev/null || err "missing python3-tk  (sudo apt install python3-tk)"
python3 -c "import PIL" 2>/dev/null      || err "missing Pillow  (pip install pillow --break-system-packages)"
python3 -c "import pystray" 2>/dev/null  || err "missing pystray (pip install pystray --break-system-packages)"
# DejaVu Mono is used throughout the UI — warn if missing (non-fatal; falls back to system mono)
fc-list 2>/dev/null | grep -qi "DejaVu" || \
    info "optional: DejaVu fonts not found — install with: sudo apt install fonts-dejavu"

# ── Paths ─────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN=/usr/local/bin
DESKTOP="$HOME/.local/share/applications"
POLKIT_DIR=/etc/polkit-1/rules.d
POLKIT_RULE="$POLKIT_DIR/50-vpn-launcher-kill.rules"

# ── Main script ───────────────────────────────────────────────────────────
info "Installing vpn-launcher → $BIN/vpn-launcher"
sudo install -m 755 "$SCRIPT_DIR/vpn_launcher.py" "$BIN/vpn-launcher"
ok "vpn-launcher installed"

# ── Icon ──────────────────────────────────────────────────────────────────
info "Installing icon → $BIN/vpn_launcher_icon_v3.png"
sudo install -m 644 "$SCRIPT_DIR/vpn_launcher_icon_v3.png" "$BIN/vpn_launcher_icon_v3.png"
ok "icon installed"

# ── Polkit rule — allows passwordless disconnect for the installing user ───
# The GUI runs as your user but openvpn runs as root (spawned via pkexec).
# To disconnect, the app runs `pkexec sh -c 'pkill openvpn'` inline.
# Without this rule pkexec would prompt for a password on every disconnect.
# The rule is scoped to the current user (${SUDO_USER:-$USER}) only —
# other users on the same machine are unaffected.
INSTALL_USER="${SUDO_USER:-$USER}"
if [ -d "$POLKIT_DIR" ]; then
    info "Installing polkit rule → $POLKIT_RULE  (scoped to user: $INSTALL_USER)"
    # Resolve absolute paths for sh and wg-quick so the rule is as narrow as possible.
    SH_PATH="$(command -v sh)"
    WGQUICK_PATH="$(command -v wg-quick)"
    sudo tee "$POLKIT_RULE" > /dev/null << EOF
// Allow $INSTALL_USER to run pkexec for openvpn disconnect (sh) and WireGuard (wg-quick)
// without a password prompt. Scoped to the exact binaries and the installing user only.
// Installed by vpn-launcher install.sh — safe to remove with uninstall.sh.
polkit.addRule(function(action, subject) {
    if (action.id === "org.freedesktop.policykit.exec" &&
        subject.user === "$INSTALL_USER" &&
        subject.local && subject.active) {
        var prog = action.lookup("program");
        if (prog === "$SH_PATH" || prog === "$WGQUICK_PATH") {
            return polkit.Result.YES;
        }
    }
});
EOF
    sudo chmod 644 "$POLKIT_RULE"
    ok "polkit rule installed (passwordless disconnect enabled for $INSTALL_USER)"
else
    info "Polkit rules.d not found — skipping (disconnect will prompt for password)"
fi

# ── Desktop entry ─────────────────────────────────────────────────────────
info "Installing desktop entry → $DESKTOP/VPN_Launcher.desktop"
mkdir -p "$DESKTOP"
tee "$DESKTOP/VPN_Launcher.desktop" > /dev/null << 'EOF'
[Desktop Entry]
Version=1.0
Type=Application
Name=VPN Launcher
Comment=One-click OpenVPN GUI for THM, HTB and OffSec
Exec=vpn-launcher
Icon=/usr/local/bin/vpn_launcher_icon_v3.png
Terminal=false
Categories=Network;Security;
StartupNotify=true
EOF
chmod +x "$DESKTOP/VPN_Launcher.desktop"
update-desktop-database "$DESKTOP" 2>/dev/null || true
ok "desktop entry installed"

# ── Desktop shortcut ──────────────────────────────────────────────────────
DESK_SHORTCUT="$HOME/Desktop/VPN_Launcher.desktop"
if [ -d "$HOME/Desktop" ]; then
    info "Placing shortcut on desktop → $DESK_SHORTCUT"
    cp "$DESKTOP/VPN_Launcher.desktop" "$DESK_SHORTCUT"
    chmod +x "$DESK_SHORTCUT"
    # Mark trusted so GNOME/Nautilus launches it without the "Allow Launching" prompt
    gio set "$DESK_SHORTCUT" metadata::trusted true 2>/dev/null || true
    ok "desktop shortcut placed"
else
    info "No ~/Desktop found — skipping desktop shortcut"
fi

# ── Default VPN folder ────────────────────────────────────────────────────
VPN_DIR="$HOME/Desktop/vpn"
if [ ! -d "$VPN_DIR" ]; then
    info "Creating default VPN folder → $VPN_DIR"
    mkdir -p "$VPN_DIR"
    ok "created $VPN_DIR — drop your .ovpn files here"
fi

echo ""
ok "VPN Launcher Pro installed successfully"
echo -e "   Run from terminal:   ${G}vpn-launcher${N}"
echo -e "   Or launch from your application menu"
