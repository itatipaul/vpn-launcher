#!/usr/bin/env bash
# VPN Launcher Pro — uninstaller
set -e

G='\033[0;32m'; B='\033[1;34m'; R='\033[0;31m'; N='\033[0m'
info()  { echo -e "${B}[*]${N} $*"; }
ok()    { echo -e "${G}[-]${N} $*"; }

BIN=/usr/local/bin
DESKTOP="$HOME/.local/share/applications"
POLKIT_RULE=/etc/polkit-1/rules.d/50-vpn-launcher-kill.rules
CONFIG_DIR="$HOME/.config/vpn-launcher"

# Kill any running instance first
if pgrep -x openvpn &>/dev/null; then
    info "Stopping running openvpn processes..."
    pkexec pkill -x openvpn || sudo pkill -x openvpn || true
    ok "openvpn stopped"
fi

# Remove installed files
for f in "$BIN/vpn-launcher" \
          "$BIN/vpn_launcher_icon_v3.png" \
          "$DESKTOP/VPN_Launcher.desktop" \
          "$HOME/Desktop/VPN_Launcher.desktop" \
          "$POLKIT_RULE"; do
    if [ -e "$f" ]; then
        info "Removing $f"
        case "$f" in
            /usr/local/bin/*|/etc/*) sudo rm -f "$f" ;;
            *) rm -f "$f" ;;
        esac
        ok "removed $f"
    fi
done

# Remove saved config (folder preference etc.)
if [ -d "$CONFIG_DIR" ]; then
    info "Removing config dir $CONFIG_DIR"
    rm -rf "$CONFIG_DIR"
    ok "removed config dir"
fi

update-desktop-database "$DESKTOP" 2>/dev/null || true

echo ""
ok "VPN Launcher Pro uninstalled"
echo "   Your .ovpn files in ~/Desktop/vpn/ were not touched."
