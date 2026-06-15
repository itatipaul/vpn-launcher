#!/usr/bin/env bash
# VPN Launcher Pro — uninstaller
set -e

G='\033[0;32m'; B='\033[1;34m'; R='\033[0;31m'; N='\033[0m'
info()  { echo -e "${B}[*]${N} $*"; }
ok()    { echo -e "${G}[-]${N} $*"; }

BIN=/usr/local/bin
DESKTOP="$HOME/.local/share/applications"
POLKIT_RULE=/etc/polkit-1/rules.d/50-vpn-launcher-kill.rules

# ── Tear down any live VPN connections ─────────────────────────────────────

# Stop OpenVPN — use the same TERM→wait→KILL pattern as the app itself
# so we don't leave root-owned processes behind.
if pgrep -x openvpn &>/dev/null; then
    info "Stopping running openvpn processes..."
    pkexec sh -c '
        pkill -TERM -x openvpn 2>/dev/null || true
        i=0
        while [ "$i" -lt 16 ]; do
            pgrep -x openvpn >/dev/null 2>&1 || exit 0
            sleep 0.3
            i=$((i+1))
        done
        pkill -KILL -x openvpn 2>/dev/null || true
    ' || sudo pkill -x openvpn 2>/dev/null || true
    ok "openvpn stopped"
fi

# Bring down any WireGuard interfaces that the app may have raised.
# We look for active wg interfaces via `wg show interfaces` and bring each down.
if command -v wg &>/dev/null; then
    WG_IFACES="$(wg show interfaces 2>/dev/null || true)"
    if [ -n "$WG_IFACES" ]; then
        info "Bringing down active WireGuard interfaces: $WG_IFACES"
        for iface in $WG_IFACES; do
            pkexec wg-quick down "$iface" 2>/dev/null || \
                sudo wg-quick down "$iface" 2>/dev/null || true
            ok "wg interface $iface down"
        done
    fi
fi

# ── Remove installed files ─────────────────────────────────────────────────
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

update-desktop-database "$DESKTOP" 2>/dev/null || true

echo ""
ok "VPN Launcher Pro uninstalled"
echo "   Your .ovpn / .conf files in ~/Desktop/vpn/ were not touched."
