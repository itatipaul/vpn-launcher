# VPN Launcher Pro

A simple GUI for switching between OpenVPN profiles on Linux — no terminal required.

Built for people who use **HackTheBox**, **TryHackMe**, **OffSec/PG** and similar platforms where you juggle multiple `.ovpn` files and want to connect without typing `sudo openvpn --config ...` every time.

```
┌─[ VPN-LAUNCHER-PRO ]─────────────────────────── [ CONNECTED ]
│                     │  STATUS      TUNNEL-IP       UPTIME
│ [ FOLDER ]          │  ─────────────────────────────────────
│ ~/Desktop/vpn       │  ONLINE      10.10.14.25     00:12:33
│ [browse] [reload]   │
│                     │  ┌─ [ OPENVPN LOG ] ──────────────────
│ [ PROFILES ]        │  [13:10:20] Initialization Sequence..
│ > search…           │  [13:10:20] tunnel ip ▸ 10.10.14.25
│                     │
│ 01  htb.ovpn        │
│ 02  offsec.ovpn ◀   │
│ 03  thm.ovpn        │
│ ─────────────────── │
│ [ CONNECT ]         │
│ [ DISCONNECT ]      │
└─────────────────────┴────────────────────────────────────────
 █  tunnel up  ▸  offsec.ovpn              vpn-launcher-pro v3.1
```

---

## Why

Every time you switch between HTB, THM, or OffSec you have to:

1. Find the right `.ovpn` file
2. Open a terminal
3. Type `sudo openvpn --config ~/Downloads/htb-eu-whatever.ovpn`
4. Keep that terminal open
5. Repeat for every switch

This replaces all of that with a desktop icon you double-click. Pick a profile, click Connect, done. The terminal log is still visible inside the app if you need to debug, but you never have to touch a terminal to use it.

---

## Features

- One-click connect and disconnect from the desktop
- Supports **OpenVPN** (`.ovpn`) and **WireGuard** (`.conf`) profiles
- Loads all profiles from a folder automatically — each tagged `[ovpn]` or `[wg]`
- Live colour-coded OpenVPN log inside the app
- Shows tunnel IP, connection status, and session uptime
- Search box to filter profiles by name
- Minimises to system tray — stays running in the background
- No terminal needed after setup

---

## Requirements

- Linux (Kali, Ubuntu, Debian, Arch, etc.)
- X11 or XWayland
- `openvpn`
- `polkit` / `pkexec` — for the privilege prompt when connecting
- `python3-tk` — Tkinter GUI library
- `fonts-dejavu` — monospace font used by the UI
- `iproute2` — for the `ip` command (pre-installed on all major distros)
- `python3-pillow` / `Pillow` — image resizing for the window icon (avoids X11 `BadLength` on large PNGs)
- `pystray` — system tray icon (minimise to tray instead of closing)
- `wireguard-tools` — for WireGuard support (`wg-quick`)

---

## Installation

### 1. Install dependencies

**Kali / Debian / Ubuntu:**
```bash
sudo apt update
sudo apt install openvpn wireguard-tools policykit-1 python3-tk fonts-dejavu
pip install pillow pystray --break-system-packages
```

**Arch / Manjaro:**
```bash
sudo pacman -S openvpn wireguard-tools polkit python-tk ttf-dejavu
pip install pillow pystray
```

**Fedora:**
```bash
sudo dnf install openvpn wireguard-tools polkit python3-tkinter dejavu-sans-mono-fonts
pip install pillow pystray
```

### 2. Clone the repo

```bash
git clone https://github.com/itatipaul/vpn-launcher.git
cd vpn-launcher
```

### 3. Run the installer

```bash
chmod +x install.sh
./install.sh
```

The installer sets up everything in one shot:

- Copies `vpn_launcher.py` to `/usr/local/bin/vpn-launcher` (available system-wide on PATH)
- Installs a polkit rule scoped to your user so disconnect requires no password prompt
- Installs the desktop entry to `~/.local/share/applications/`
- Places a shortcut on `~/Desktop/` and marks it trusted (no "Allow Launching" prompt on GNOME)
- Creates `~/Desktop/vpn/` if it doesn't exist yet

### 4. Drop in your VPN profiles

```bash
cp ~/Downloads/*.ovpn ~/Desktop/vpn/
cp ~/Downloads/*.conf ~/Desktop/vpn/
```

The app defaults to `~/Desktop/vpn/`. It loads both `.ovpn` (OpenVPN) and `.conf` (WireGuard) files automatically. You can point it at any folder using the **[browse]** button inside the app.

### 5. Launch

```bash
vpn-launcher
```

Or find **VPN Launcher** in your application menu.

---

## Uninstalling

```bash
./uninstall.sh
```

Removes the binary, kill script, polkit rule, and desktop entry. Your `.ovpn` files are left untouched.

---

## How disconnect works

OpenVPN runs as root (spawned via `pkexec`). Since root-owned processes can't be signalled from a user-space GUI, disconnect uses `pkexec` to run an inline shell script as root that sends SIGTERM, waits up to ~5 seconds, then escalates to SIGKILL if needed:

```
GUI (your user)  →  pkexec sh -c 'pkill -TERM openvpn; sleep…; pkill -KILL openvpn'  →  kills root-owned openvpn ✓
```

The polkit rule installed by `install.sh` allows this without a password prompt for the installing user. No separate helper script is installed — the kill logic runs entirely inline.

---

## Usage

### Connecting

1. Open VPN Launcher from your desktop or app menu
2. Your `.ovpn` profiles are listed in the left sidebar
3. Click a profile to select it
4. Click **[ CONNECT ]**
5. Enter your password in the `pkexec` prompt that appears
6. Wait for the log to show `Initialization Sequence Completed`
7. Status flips to **ONLINE**, tunnel IP appears automatically

### Disconnecting

Click **[ DISCONNECT ]**. The tunnel closes, status returns to **OFFLINE**, and the uptime resets.

### Switching between platforms

Click a different profile and hit **[ CONNECT ]** — if you are already connected, disconnect first, then reconnect with the new profile.

### Using a different folder

If your `.ovpn` files are not in `~/Desktop/vpn/`, click **[browse]** to pick a different folder, or type the path directly into the folder field and click **[reload]**. The app remembers the path for the current session.

### WireGuard profiles

WireGuard `.conf` files are loaded alongside OpenVPN `.ovpn` files. Each profile in the list is tagged `[ovpn]` or `[wg]` so you always know what you're connecting to.

For WireGuard, the interface name is derived from the filename — `wg0.conf` brings up interface `wg0`. Connect and disconnect work the same way as OpenVPN.

### Minimising to tray

Closing the window minimises the app to the system tray rather than quitting it. The tray icon shows the current connection state in its tooltip. Right-click the tray icon for a menu:

- **Show VPN Launcher** — restore the window (also triggered by double-clicking the icon)
- **Connect / Disconnect** — control the VPN without opening the window
- **Quit** — fully exit the app

If `pystray` is not installed, closing the window quits the app instead.

### Searching profiles

Type in the `> search…` box to filter the profile list by name in real time — useful when you have many `.ovpn` files across different platforms or regions.

---

## How it works

### No root GUI

OpenVPN needs root to create `tun` interfaces and modify routing tables. Rather than running the whole app as root, only the `openvpn` subprocess is elevated using `pkexec`:

```
GUI (your user)  →  pkexec  →  openvpn (root)
```

`pkexec` is the Polkit equivalent of `sudo` and shows a graphical password prompt so you never need a terminal.

### Log streaming

OpenVPN's output is streamed line-by-line into the log pane in real time. Lines are colour-coded automatically:

| Colour | Meaning |
|--------|---------|
| Bright green | Tunnel established |
| Amber | Warning |
| Red | Error |
| Dim green | Info / normal output |

### Tunnel IP detection

Once the tunnel is up, the app scans all `tun*` interfaces via `ip -4 addr` to find the assigned IP — more reliable than parsing log lines, and handles numbered interfaces (`tun1`, `tun2`, etc.) automatically. It retries for ~6 seconds to allow the kernel time to finish configuring the interface.

### Disconnect

Disconnect runs an inline shell script via `pkexec sh -c '...'` as root. The script sends SIGTERM to openvpn, waits up to ~5 seconds for a clean exit, then escalates to SIGKILL if the process is still alive. This kills all openvpn processes cleanly regardless of how they were spawned. The polkit rule installed by `install.sh` allows this without a password prompt for the installing user.

---

## File structure

```
repo/
├── vpn_launcher.py          ← main app
├── vpn_launcher_icon_v3.png ← app icon
├── requirements.txt         ← Python dependencies
├── install.sh               ← installer
└── uninstall.sh             ← uninstaller

after install:
/usr/local/bin/
├── vpn-launcher                 ← main app (on PATH)
└── vpn_launcher_icon_v3.png     ← window/taskbar icon

/etc/polkit-1/rules.d/
└── 50-vpn-launcher-kill.rules   ← passwordless disconnect for your user

~/.local/share/applications/
└── VPN_Launcher.desktop         ← app menu entry

~/Desktop/
└── VPN_Launcher.desktop         ← desktop shortcut (trusted, double-click to launch)

~/Desktop/vpn/        ← default profiles folder (created by installer)
├── htb.ovpn
├── offsec.ovpn
├── thm.ovpn
└── wg0.conf
```

---

## Troubleshooting

**Password prompt doesn't appear / nothing happens on Connect**

Make sure `polkit` is installed and a Polkit agent is running. On minimal Kali installs:
```bash
sudo apt install policykit-1
/usr/lib/polkit-gnome/polkit-gnome-authentication-agent-1 &
```

**`No module named tkinter`**
```bash
sudo apt install python3-tk
```

**Tunnel IP shows `───────` after connecting**

The app scans all `tun*` interfaces automatically, so numbered interfaces like `tun3` or `tun4` are handled. If the IP still doesn't appear after ~6 seconds, check the log for which interface was opened and verify it with `ip -4 addr`.

**App won't launch**

```bash
vpn-launcher   # run from terminal to see any errors
```

If you get a `command not found`, re-run `./install.sh`.

**Tray icon doesn't appear after closing the window**

Make sure `pystray` is installed and a system tray is running:
```bash
pip install pystray --break-system-packages
```
On minimal Kali installs without a tray (e.g. bare i3/bspwm), install one:
```bash
sudo apt install trayer
trayer &
```
If `pystray` is absent the app falls back to quitting on close — no tray, but no crash.

**Window icon doesn't appear / X11 `BadLength` error**

The PNG icon is resized to 64×64 at runtime using Pillow. If Pillow is missing you may see a `BadLength` X error or a silent launch failure:
```bash
pip install pillow --break-system-packages
```

**`DejaVu Sans Mono` font looks wrong or falls back**
```bash
sudo apt install fonts-dejavu
```

**WireGuard interface won't come up**

Make sure `wireguard-tools` is installed:
```bash
sudo apt install wireguard-tools
```
Check that your `.conf` file is valid with:
```bash
sudo wg-quick up ~/Desktop/vpn/wg0.conf
```

**Ghost wg interfaces after a crash**

If the app crashed without disconnecting a WireGuard tunnel:
```bash
sudo wg-quick down ~/Desktop/vpn/wg0.conf
```

**Ghost tun interfaces after a crash**

If the app crashed without disconnecting, old `tun` interfaces may be left behind. Clean them up manually:
```bash
sudo pkill openvpn
sudo ip link delete tun0   # repeat for tun1, tun2, etc. as needed
```

---

## Tested on

- Kali Linux 2025.x — GNOME on XWayland
- OpenVPN 2.7.x
- HTB, THM, and OffSec/PG `.ovpn` profiles

---

## License

MIT
