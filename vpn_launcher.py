#!/usr/bin/env python3
"""
VPN Launcher Pro  —  Terminal / TUI aesthetic
Pure tkinter, zero extra deps. Works on X11 and XWayland.
"""

import tkinter as tk
from tkinter import filedialog, messagebox
import subprocess, threading, os, glob, time
try:
    import pystray
    from PIL import Image as PILImage
    _TRAY_AVAILABLE = True
except ImportError:
    _TRAY_AVAILABLE = False

# ── Palette ────────────────────────────────────────────────────────────────
BG       = "#0c0c0c"
SURFACE  = "#111111"
BORDER   = "#1f6f3a"
ACCENT   = "#00ff41"
DIM      = "#1a4028"
TEXT     = "#c8ffd4"
MUTED    = "#3a7a4a"
WARN     = "#f5c842"
DANGER   = "#ff4466"
SUCCESS  = "#00ff41"
LOG_BG   = "#060c08"
LOG_FG   = "#33ff88"

FONT_MONO  = ("DejaVu Sans Mono", 10)
FONT_MONO_B= ("DejaVu Sans Mono", 10, "bold")
FONT_MONO_S= ("DejaVu Sans Mono", 9)
FONT_MONO_SB=("DejaVu Sans Mono", 9, "bold")


class VPNLauncher(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("vpn-launcher")
        self.geometry("900x600")
        self.minsize(780, 500)
        self.configure(bg=BG)

        self.vpn_dir   = os.path.expanduser("~/Desktop/vpn")
        self.process   = None
        self._active_profile = None
        self._active_type    = None   # 'ovpn' | 'wg'
        self._profiles = []
        self._selected = None
        self._profile_rows = []
        self._start_ts = None
        self._timer_id = None
        self._blink_id = None
        self._blink_on  = True
        self._tray_icon = None
        self._tray_thread = None

        self._build()
        self.load_profiles()
        self._blink_cursor()
        self.after(100, self._set_window_icon)  # defer until window is mapped
        self.protocol("WM_DELETE_WINDOW", self._on_close)


    # ── System tray ────────────────────────────────────────────────────────

    def _on_close(self):
        """Minimise to tray if pystray is available, otherwise quit."""
        if _TRAY_AVAILABLE:
            self._minimise_to_tray()
        else:
            self._quit_app()

    def _minimise_to_tray(self):
        """Hide the window and start the tray icon in a daemon thread."""
        self.withdraw()
        if self._tray_icon is not None:
            return  # already running

        script_dir = os.path.dirname(os.path.abspath(__file__))
        icon_path  = os.path.join(script_dir, "vpn_launcher_icon_v3.png")
        try:
            img = PILImage.open(icon_path).resize((64, 64), PILImage.LANCZOS)
        except Exception:
            # Fallback: solid green square
            img = PILImage.new("RGB", (64, 64), color="#00ff41")

        def on_show(icon, item):
            icon.stop()
            self._tray_icon = None
            self.after(0, self.deiconify)

        def on_connect(icon, item):
            self.after(0, self.connect)

        def on_disconnect(icon, item):
            self.after(0, self.disconnect)

        def on_quit(icon, item):
            icon.stop()
            self._tray_icon = None
            self.after(0, self._quit_app)

        menu = pystray.Menu(
            pystray.MenuItem("Show VPN Launcher", on_show, default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Connect",    on_connect),
            pystray.MenuItem("Disconnect", on_disconnect),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit",       on_quit),
        )

        self._tray_icon = pystray.Icon(
            "vpn-launcher",
            img,
            "VPN Launcher Pro",
            menu
        )

        self._tray_thread = threading.Thread(
            target=self._tray_icon.run,
            daemon=True
        )
        self._tray_thread.start()

    def _update_tray_title(self, connected=False, profile=""):
        """Update the tray tooltip to reflect connection state."""
        if self._tray_icon is None:
            return
        if connected:
            self._tray_icon.title = f"VPN Launcher Pro — CONNECTED  ▸  {profile}"
        else:
            self._tray_icon.title = "VPN Launcher Pro — DISCONNECTED"

    def _quit_app(self):
        """Cleanly destroy the window and exit."""
        if self._tray_icon:
            self._tray_icon.stop()
            self._tray_icon = None
        self.destroy()

    # ── Window icon ────────────────────────────────────────────────────────

    def _set_window_icon(self):
        """Set the window/taskbar icon — resized to 64x64 to avoid X11 BadLength."""
        script_dir = os.path.dirname(os.path.abspath(__file__))
        icon_path  = os.path.join(script_dir, "vpn_launcher_icon_v3.png")
        if not os.path.isfile(icon_path):
            self.write_log(f"icon not found: {icon_path}", "dim")
            return
        try:
            from PIL import Image, ImageTk
            pil_img = Image.open(icon_path).resize((64, 64), Image.LANCZOS)
            img = ImageTk.PhotoImage(pil_img)
            self.iconphoto(True, img)
            self._icon_img = img   # keep a reference — GC will drop it otherwise
        except Exception as e:
            self.write_log(f"icon load failed: {e}", "dim")

    # ── Master layout ──────────────────────────────────────────────────────

    def _build(self):
        # Title bar
        self._build_titlebar()

        # Body row — sidebar + divider + main, all filling height
        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True)

        # Sidebar fixed width
        self._build_sidebar(body)

        # 1px vertical divider
        tk.Frame(body, bg=BORDER, width=1).pack(side="left", fill="y", pady=4)

        # Main fills the rest
        self._build_main(body)

        # Status bar
        self._build_statusbar()

    # ── Title bar ──────────────────────────────────────────────────────────

    def _build_titlebar(self):
        bar = tk.Frame(self, bg=SURFACE)
        bar.pack(fill="x")

        tk.Label(bar, text="┌─[ VPN-LAUNCHER-PRO ]",
                 font=FONT_MONO_B, bg=SURFACE, fg=ACCENT).pack(
            side="left", padx=8, pady=5)

        self._title_status = tk.Label(bar, text="[ DISCONNECTED ]",
                 font=FONT_MONO_B, bg=SURFACE, fg=MUTED)
        self._title_status.pack(side="right", padx=8, pady=5)

        tk.Frame(self, bg=BORDER, height=1).pack(fill="x")

    # ── Sidebar ────────────────────────────────────────────────────────────

    def _build_sidebar(self, parent):
        sb = tk.Frame(parent, bg=BG, width=210)
        sb.pack(side="left", fill="y")
        sb.pack_propagate(False)

        # Folder section
        tk.Label(sb, text="[ FOLDER ]", font=FONT_MONO_B,
                 bg=BG, fg=MUTED, anchor="w").pack(
            fill="x", padx=8, pady=(8, 2))

        self.folder_var = tk.StringVar(value=self.vpn_dir)
        fe = tk.Entry(sb, textvariable=self.folder_var,
                      font=FONT_MONO_S, bg="#0a1a10", fg=TEXT,
                      insertbackground=ACCENT, relief="flat", bd=0,
                      highlightthickness=1,
                      highlightcolor=BORDER, highlightbackground=BORDER)
        fe.pack(fill="x", padx=8, ipady=3)

        btn_row = tk.Frame(sb, bg=BG)
        btn_row.pack(fill="x", padx=8, pady=4)
        self._tui_btn(btn_row, "[browse]", self.choose_folder).pack(
            side="left", padx=(0, 4))
        self._tui_btn(btn_row, "[reload]", self.load_profiles).pack(side="left")

        # Divider
        tk.Frame(sb, bg=BORDER, height=1).pack(fill="x", padx=8, pady=4)

        # Profiles section
        tk.Label(sb, text="[ PROFILES ]", font=FONT_MONO_B,
                 bg=BG, fg=MUTED, anchor="w").pack(
            fill="x", padx=8, pady=(0, 2))

        # Search
        srch_frame = tk.Frame(sb, bg="#0a1a10",
                              highlightthickness=1,
                              highlightbackground=BORDER)
        srch_frame.pack(fill="x", padx=8, pady=(0, 4))

        tk.Label(srch_frame, text="> ", font=FONT_MONO_S,
                 bg="#0a1a10", fg=ACCENT).pack(side="left", padx=(4, 0))
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._filter_list())
        tk.Entry(srch_frame, textvariable=self.search_var,
                 font=FONT_MONO_S, bg="#0a1a10", fg=TEXT,
                 insertbackground=ACCENT, relief="flat", bd=0).pack(
            side="left", fill="x", expand=True, ipady=3, padx=(0, 4))

        # Profile list — scrollable, expands to fill remaining space
        list_wrap = tk.Frame(sb, bg=BG)
        list_wrap.pack(fill="both", expand=True, padx=8)

        vsb = tk.Scrollbar(list_wrap, orient="vertical",
                           bg=SURFACE, troughcolor=BG,
                           activebackground=ACCENT, width=6,
                           relief="flat", bd=0)
        self._list_canvas = tk.Canvas(list_wrap, bg=BG,
                                      highlightthickness=0,
                                      yscrollcommand=vsb.set)
        vsb.configure(command=self._list_canvas.yview)
        vsb.pack(side="right", fill="y")
        self._list_canvas.pack(side="left", fill="both", expand=True)

        self._list_inner = tk.Frame(self._list_canvas, bg=BG)
        self._list_win = self._list_canvas.create_window(
            (0, 0), window=self._list_inner, anchor="nw")
        self._list_inner.bind("<Configure>", self._on_list_resize)
        self._list_canvas.bind("<Configure>", self._on_canvas_resize)

        # Divider above buttons
        tk.Frame(sb, bg=BORDER, height=1).pack(fill="x", padx=8, pady=(4, 4))

        # Connect / Disconnect — fixed at bottom
        self._tui_btn(sb, "[ CONNECT ]", self.connect,
                      fg=ACCENT, active_fg=BG, active_bg=ACCENT).pack(
            fill="x", padx=8, pady=(0, 3), ipady=4)
        self._tui_btn(sb, "[ DISCONNECT ]", self.disconnect,
                      fg=DANGER, active_fg=BG, active_bg=DANGER).pack(
            fill="x", padx=8, pady=(0, 8), ipady=4)

    def _on_list_resize(self, e):
        self._list_canvas.configure(
            scrollregion=self._list_canvas.bbox("all"))

    def _on_canvas_resize(self, e):
        self._list_canvas.itemconfig(self._list_win, width=e.width)

    # ── Main panel ─────────────────────────────────────────────────────────

    def _build_main(self, parent):
        main = tk.Frame(parent, bg=BG)
        main.pack(side="left", fill="both", expand=True,
                  padx=(6, 6), pady=4)

        # Stats row — fixed height
        stats = tk.Frame(main, bg=BG)
        stats.pack(fill="x", pady=(0, 4))

        self._lbl_status = self._stat_block(stats, "STATUS",   "OFFLINE",   MUTED)
        self._lbl_ip     = self._stat_block(stats, "TUNNEL-IP","───────",   MUTED)
        self._lbl_uptime = self._stat_block(stats, "UPTIME",   "00:00:00",  MUTED)

        # Log header — single line
        log_hdr = tk.Frame(main, bg=BG)
        log_hdr.pack(fill="x")
        self._log_hdr_lbl = tk.Label(log_hdr, text="",
                                      font=FONT_MONO_S, bg=BG, fg=BORDER,
                                      anchor="w")
        self._log_hdr_lbl.pack(fill="x")
        log_hdr.bind("<Configure>", self._redraw_log_hdr)

        # Log text — fills all remaining space
        log_outer = tk.Frame(main, bg=BG)
        log_outer.pack(fill="both", expand=True)

        vsb = tk.Scrollbar(log_outer, bg=SURFACE,
                           troughcolor=BG, activebackground=ACCENT,
                           width=6, relief="flat", bd=0)
        self.log = tk.Text(log_outer,
                           font=("DejaVu Sans Mono", 9),
                           bg=LOG_BG, fg=LOG_FG,
                           insertbackground=ACCENT,
                           selectbackground=DIM, selectforeground=ACCENT,
                           relief="flat", bd=0, wrap="word",
                           state="disabled",
                           yscrollcommand=vsb.set)
        vsb.configure(command=self.log.yview)
        vsb.pack(side="right", fill="y")
        self.log.pack(side="left", fill="both", expand=True)

        self.log.tag_configure("ok",   foreground=ACCENT)
        self.log.tag_configure("info", foreground=LOG_FG)
        self.log.tag_configure("warn", foreground=WARN)
        self.log.tag_configure("err",  foreground=DANGER)
        self.log.tag_configure("dim",  foreground=MUTED)

    def _stat_block(self, parent, label, value, color):
        f = tk.Frame(parent, bg=SURFACE,
                     highlightthickness=1, highlightbackground=BORDER)
        f.pack(side="left", fill="x", expand=True,
               padx=(0, 4), ipadx=10, ipady=6)
        tk.Label(f, text=label, font=("DejaVu Sans Mono", 8, "bold"),
                 bg=SURFACE, fg=MUTED).pack(anchor="w", padx=8, pady=(5,0))
        lbl = tk.Label(f, text=value,
                       font=("DejaVu Sans Mono", 13, "bold"),
                       bg=SURFACE, fg=color)
        lbl.pack(anchor="w", padx=8, pady=(0,5))
        return lbl

    def _redraw_log_hdr(self, e):
        # Recalculate box-drawing header to match actual pixel width
        # Approximate char width for DejaVu Mono 9pt ≈ 7px
        chars = max(10, e.width // 7)
        title = "[ VPN LOG ]"
        dashes = chars - len(title) - 3   # 3 = "┌─ "
        line = f"┌─ {title} " + "─" * max(0, dashes)
        self._log_hdr_lbl.configure(text=line)

    # ── Status bar ─────────────────────────────────────────────────────────

    def _build_statusbar(self):
        tk.Frame(self, bg=BORDER, height=1).pack(fill="x")
        bar = tk.Frame(self, bg=SURFACE)
        bar.pack(fill="x")

        self._cursor_lbl = tk.Label(bar, text="█",
                                    font=FONT_MONO_S, bg=SURFACE, fg=ACCENT)
        self._cursor_lbl.pack(side="left", padx=(8, 2), pady=3)

        self._status_bar_text = tk.Label(
            bar, text="ready — select a profile and press [ CONNECT ]",
            font=FONT_MONO_S, bg=SURFACE, fg=MUTED)
        self._status_bar_text.pack(side="left", pady=3)

        tk.Label(bar, text="vpn-launcher-pro v1.0",
                 font=FONT_MONO_S, bg=SURFACE, fg=MUTED).pack(
            side="right", padx=8, pady=3)

    # ── Helpers ────────────────────────────────────────────────────────────

    def _tui_btn(self, parent, text, cmd,
                 fg=TEXT, active_fg=BG, active_bg=ACCENT):
        b = tk.Button(parent, text=text, font=FONT_MONO_B,
                      bg=BG, fg=fg, relief="flat", bd=0,
                      activebackground=active_bg, activeforeground=active_fg,
                      cursor="hand2", command=cmd,
                      highlightthickness=1,
                      highlightbackground=BORDER, highlightcolor=ACCENT)
        b.bind("<Enter>", lambda e: b.configure(bg=DIM, fg=active_bg if active_bg != BG else ACCENT))
        b.bind("<Leave>", lambda e: b.configure(bg=BG, fg=fg))
        return b

    def _blink_cursor(self):
        self._blink_on = not self._blink_on
        self._cursor_lbl.configure(fg=ACCENT if self._blink_on else SURFACE)
        self._blink_id = self.after(530, self._blink_cursor)

    # ── Profile list ───────────────────────────────────────────────────────

    def _clear_list(self):
        for w in self._profile_rows:
            w.destroy()
        self._profile_rows.clear()

    def _filter_list(self):
        q = self.search_var.get().lower()
        for row in self._profile_rows:
            name = row._name
            if q in name.lower():
                row.pack(fill="x", pady=1)
            else:
                row.pack_forget()

    def _add_profile_row(self, name, idx, kind="ovpn"):
        row = tk.Frame(self._list_inner, bg=BG)
        row._name = name
        row._kind = kind
        row.pack(fill="x", pady=1)

        idx_lbl = tk.Label(row, text=f"{idx:02d}",
                           font=FONT_MONO_S, bg=BG, fg=MUTED, width=3,
                           anchor="e")
        idx_lbl.pack(side="left", padx=(4, 0))

        name_lbl = tk.Label(row, text=name, font=FONT_MONO_S,
                            bg=BG, fg=TEXT, anchor="w",
                            cursor="hand2", padx=6, pady=3)
        name_lbl.pack(side="left", fill="x", expand=True)

        badge_text  = "[wg]"    if kind == "wg" else "[ovpn]"
        badge_color = "#00d4ff" if kind == "wg" else MUTED
        kind_lbl = tk.Label(row, text=badge_text, font=FONT_MONO_S,
                            bg=BG, fg=badge_color, padx=4)
        kind_lbl.pack(side="right", padx=(0, 4))

        def on_click(e, n=name):
            self._select_profile(n)

        def on_enter(e, r=row, nl=name_lbl, il=idx_lbl, kl=kind_lbl):
            if self._selected != r._name:
                r.configure(bg=DIM)
                nl.configure(bg=DIM, fg=ACCENT)
                il.configure(bg=DIM)
                kl.configure(bg=DIM)

        def on_leave(e, r=row, nl=name_lbl, il=idx_lbl, kl=kind_lbl):
            active = self._selected == r._name
            c = DIM if active else BG
            r.configure(bg=c); nl.configure(bg=c)
            il.configure(bg=c); kl.configure(bg=c)
            nl.configure(fg=ACCENT if active else TEXT)

        for w in (row, name_lbl, idx_lbl, kind_lbl):
            w.bind("<Button-1>", on_click)
            w.bind("<Enter>", on_enter)
            w.bind("<Leave>", on_leave)

        self._profile_rows.append(row)

    def _select_profile(self, name):
        self._selected = name
        for row in self._profile_rows:
            active = row._name == name
            c = DIM if active else BG
            row.configure(bg=c)
            children = row.winfo_children()
            for child in children:
                child.configure(bg=c)
                if isinstance(child, tk.Label) and child.cget("anchor") == "w":
                    child.configure(fg=ACCENT if active else TEXT)
        self._set_statusbar(f"selected  ▸  {name}")

    # ── Core logic ─────────────────────────────────────────────────────────

    def choose_folder(self):
        folder = filedialog.askdirectory(initialdir=self.folder_var.get())
        if folder:
            self.vpn_dir = folder
            self.folder_var.set(folder)
            self.load_profiles()

    def load_profiles(self):
        self.vpn_dir = self.folder_var.get()
        ovpn  = sorted(glob.glob(os.path.join(self.vpn_dir, "*.ovpn")))
        wg    = sorted(glob.glob(os.path.join(self.vpn_dir, "*.conf")))
        files = ovpn + wg
        self._profiles = files
        self._clear_list()

        if not files:
            self.write_log(f"no .ovpn or .conf files in {self.vpn_dir}", "warn")
            self._selected = None
            return

        for i, f in enumerate(files):
            name = os.path.basename(f)
            kind = "wg" if f.endswith(".conf") else "ovpn"
            self._add_profile_row(name, i + 1, kind)

        first = os.path.basename(files[0])
        self._select_profile(first)
        self.write_log(
            f"loaded {len(ovpn)} ovpn  +  {len(wg)} wireguard profile(s) from {self.vpn_dir}",
            "dim"
        )

    def write_log(self, msg, tag="info"):
        ts = time.strftime("%H:%M:%S")
        self.log.configure(state="normal")
        self.log.insert("end", f"[{ts}] ", "dim")
        self.log.insert("end", msg + "\n", tag)
        self.log.see("end")
        self.log.configure(state="disabled")

    def _set_statusbar(self, msg):
        self._status_bar_text.configure(text=msg)

    def connect(self):
        # Prevent multiple VPN instances
        if self.process and self.process.poll() is None:
            self.write_log("vpn already running", "warn")
            messagebox.showwarning(
                "VPN Running",
                "A VPN connection is already active. Disconnect it first."
            )
            return

        # Ensure a profile is selected
        if not self._selected:
            messagebox.showwarning(
                "No Profile",
                "Select a profile first."
            )
            return

        profile = os.path.join(self.vpn_dir, self._selected)

        if not os.path.isfile(profile):
            self.write_log(f"profile not found: {profile}", "err")
            messagebox.showerror(
                "Profile Missing",
                f"Profile does not exist:\n\n{profile}"
            )
            return

        # Detect protocol from filename extension
        kind = "wg" if self._selected.endswith(".conf") else "ovpn"

        # Remember the active config and type so disconnect knows what to do.
        self._active_profile = profile
        self._active_type    = kind

        self._on_connecting()

        if kind == "wg":
            self._connect_wireguard(profile)
        else:
            self._connect_openvpn(profile)

    # ── OpenVPN connect ────────────────────────────────────────────────────

    def _connect_openvpn(self, profile):
        self.write_log(f"spawning openvpn --config {self._selected}", "dim")

        def worker():
            try:
                proc = subprocess.Popen(
                    ["pkexec", "openvpn", "--config", profile],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    start_new_session=True
                )
                self.process = proc
                connected = False

                for line in proc.stdout:
                    line = line.rstrip()
                    upper = line.upper()

                    benign_route = (
                        "ROUTE EXISTS" in upper
                        or ("FILE EXISTS" in upper and "ROUTE" in upper)
                        or "RTNL" in upper
                    )

                    if benign_route:
                        tag = "dim"
                    elif "ERROR" in upper:
                        tag = "err"
                    elif "WARNING" in upper:
                        tag = "warn"
                    elif "INITIALIZATION SEQUENCE COMPLETED" in upper:
                        tag = "ok"
                    else:
                        tag = "info"

                    self.after(0, lambda l=line, t=tag: self.write_log(l, t))

                    if "INITIALIZATION SEQUENCE COMPLETED" in upper:
                        connected = True
                        self.after(0, self._on_connected)
                        self.after(0, lambda: self._fetch_tunnel_ip("tun"))

                    elif (
                        "AUTH_FAILED" in upper
                        or "TLS ERROR" in upper
                        or "AUTH FAILURE" in upper
                        or "FATAL ERROR" in upper
                    ):
                        self.after(0, lambda: (
                            self.write_log("connection failed", "err"),
                            self._title_status.configure(text="[ FAILED ]", fg=DANGER),
                            self._lbl_status.configure(text="FAILED", fg=DANGER),
                            self._set_statusbar("connection failed")
                        ))

                rc = proc.wait()
                if rc != 0 and not connected:
                    self.after(0, lambda rc=rc: self.write_log(
                        f"openvpn exited with code {rc}", "err"))

            except Exception as e:
                err = str(e)
                self.after(0, lambda err=err: (
                    self.write_log(err, "err"),
                    messagebox.showerror("OpenVPN Error", err)
                ))

        threading.Thread(target=worker, daemon=True).start()

    # ── WireGuard connect ──────────────────────────────────────────────────

    def _connect_wireguard(self, profile):
        iface = os.path.splitext(os.path.basename(profile))[0]
        self.write_log(f"bringing up wireguard interface  ▸  {iface}", "dim")

        def worker():
            try:
                proc = subprocess.Popen(
                    ["pkexec", "wg-quick", "up", profile],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    start_new_session=True
                )
                self.process = proc

                for line in proc.stdout:
                    line = line.rstrip()
                    upper = line.upper()
                    if "ERROR" in upper or "FAILED" in upper:
                        tag = "err"
                    elif "WARNING" in upper:
                        tag = "warn"
                    else:
                        tag = "info"
                    self.after(0, lambda l=line, t=tag: self.write_log(l, t))

                rc = proc.wait()

                if rc == 0:
                    self.after(0, self._on_connected)
                    self.after(0, lambda: self._fetch_tunnel_ip(iface, exact=True))
                    self.after(0, lambda: self.write_log(
                        f"wireguard tunnel up  ▸  {iface}", "ok"))
                else:
                    self.after(0, lambda rc=rc: (
                        self.write_log(f"wg-quick exited with code {rc}", "err"),
                        self._title_status.configure(text="[ FAILED ]", fg=DANGER),
                        self._lbl_status.configure(text="FAILED", fg=DANGER),
                        self._set_statusbar("wireguard failed to start")
                    ))

            except Exception as e:
                err = str(e)
                self.after(0, lambda err=err: (
                    self.write_log(err, "err"),
                    messagebox.showerror("WireGuard Error", err)
                ))

        threading.Thread(target=worker, daemon=True).start()

    def _fetch_tunnel_ip(self, iface_hint, exact=False):
        """Read tunnel IP via `ip addr`.

        iface_hint — for OpenVPN pass prefix "tun"; for WireGuard pass
                     the exact interface name (e.g. "wg0").
        exact      — if True query iface_hint directly; otherwise scan all
                     interfaces whose name starts with iface_hint.
        """
        import re
        def probe():
            for _ in range(10):
                try:
                    if exact:
                        out = subprocess.check_output(
                            ["ip", "-4", "addr", "show", iface_hint],
                            stderr=subprocess.DEVNULL, text=True)
                        m = re.search(r"inet (\d+\.\d+\.\d+\.\d+)", out)
                        if m:
                            ip = m.group(1)
                            self.after(0, lambda ip=ip: self._lbl_ip.configure(
                                text=ip, fg=SUCCESS))
                            self.after(0, lambda ip=ip: self.write_log(
                                f"tunnel ip  ▸  {ip}", "ok"))
                            return
                    else:
                        out = subprocess.check_output(
                            ["ip", "-4", "addr"],
                            stderr=subprocess.DEVNULL, text=True)
                        for block in out.split("\n\n"):
                            if iface_hint in block:
                                m = re.search(r"inet (\d+\.\d+\.\d+\.\d+)", block)
                                if m:
                                    ip = m.group(1)
                                    self.after(0, lambda ip=ip: self._lbl_ip.configure(
                                        text=ip, fg=SUCCESS))
                                    self.after(0, lambda ip=ip: self.write_log(
                                        f"tunnel ip  ▸  {ip}", "ok"))
                                    return
                except subprocess.CalledProcessError:
                    pass
                time.sleep(0.8)
            self.after(0, lambda: self.write_log(
                f"could not read ip for interface  ▸  {iface_hint}", "warn"))

        threading.Thread(target=probe, daemon=True).start()

    def _on_connecting(self):
        self._title_status.configure(text="[ CONNECTING... ]", fg=WARN)
        self._lbl_status.configure(text="CONNECTING", fg=WARN)
        self._set_statusbar("connecting…  waiting for tunnel")

    def _on_connected(self):
        self._title_status.configure(text="[ CONNECTED ]", fg=SUCCESS)
        self._lbl_status.configure(text="ONLINE", fg=SUCCESS)
        self._set_statusbar(f"tunnel up  ▸  {self._selected}")
        self._start_timer()
        self._update_tray_title(connected=True, profile=self._selected or "")

    def disconnect(self):
        if self._active_type == "wg":
            self._disconnect_wireguard()
        else:
            self._disconnect_openvpn()

    def _disconnect_openvpn(self):
        running = bool(self.process and self.process.poll() is None)
        if not running and not self._openvpn_alive():
            self.write_log("no active openvpn process", "dim")
            self._reset_disconnected_ui()
            return

        self.write_log("sending kill order to openvpn (root)", "warn")
        self._set_statusbar("disconnecting…")
        profile = self._active_profile or ""

        def worker():
            ok = self._kill_openvpn_root(profile)
            def finish():
                if self._openvpn_alive():
                    self.write_log("warning: an openvpn process may still be running", "err")
                elif ok:
                    self.write_log("all openvpn processes terminated", "ok")
                self._reset_disconnected_ui()
            self.after(0, finish)

        threading.Thread(target=worker, daemon=True).start()

    def _disconnect_wireguard(self):
        profile = self._active_profile or ""
        iface   = os.path.splitext(os.path.basename(profile))[0]

        if not profile:
            self.write_log("no active wireguard profile", "dim")
            self._reset_disconnected_ui()
            return

        self.write_log(f"bringing down wireguard interface  ▸  {iface}", "warn")
        self._set_statusbar("disconnecting wireguard…")

        def worker():
            try:
                result = subprocess.run(
                    ["pkexec", "wg-quick", "down", profile],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True
                )
                output = result.stdout.strip()
                def finish():
                    if output:
                        for line in output.splitlines():
                            self.write_log(line, "dim")
                    if result.returncode == 0:
                        self.write_log(f"wireguard interface {iface} down", "ok")
                    else:
                        self.write_log(
                            f"wg-quick down exited with code {result.returncode}", "err")
                    self._reset_disconnected_ui()
                self.after(0, finish)
            except Exception as e:
                err = str(e)
                self.after(0, lambda err=err: (
                    self.write_log(f"wg disconnect failed: {err}", "err"),
                    self._reset_disconnected_ui()
                ))

        threading.Thread(target=worker, daemon=True).start()

    def _reset_disconnected_ui(self):
        self.process = None
        self._active_profile = None

        self._stop_timer()

        self._title_status.configure(
            text="[ DISCONNECTED ]",
            fg=MUTED
        )

        self._lbl_status.configure(
            text="OFFLINE",
            fg=MUTED
        )

        self._lbl_ip.configure(
            text="───────",
            fg=MUTED
        )

        self._set_statusbar("disconnected")

        self.write_log(
            "disconnected",
            "warn"
        )
        self._update_tray_title(connected=False)

    def _openvpn_alive(self):
        """Return True if any openvpn process is currently running."""
        try:
            return subprocess.run(
                ["pgrep", "-x", "openvpn"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            ).returncode == 0
        except Exception:
            return False

    def _kill_openvpn_root(self, profile):
        """Terminate openvpn as root in a single pkexec call (one prompt).

        TERM -> wait -> KILL inside one elevated shell. Returns True on success.
        """
        # $1 = config path, passed positionally to avoid quoting issues.
        script = (
            'if [ -n "$1" ]; then '
            '  pkill -TERM -f "openvpn --config $1" 2>/dev/null; '
            'fi; '
            'pkill -TERM -x openvpn 2>/dev/null; '
            'i=0; '
            'while [ "$i" -lt 16 ]; do '
            '  pgrep -x openvpn >/dev/null 2>&1 || exit 0; '
            '  sleep 0.3; '
            '  i=$((i+1)); '
            'done; '
            'pkill -KILL -x openvpn 2>/dev/null; '
            'exit 0'
        )
        try:
            subprocess.run(
                ["pkexec", "sh", "-c", script, "sh", profile],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return True
        except Exception as e:
            self.after(0, lambda: self.write_log(f"kill failed: {e}", "err"))
            return False

    def _start_timer(self):
        self._start_ts = time.time()
        self._tick()

    def _tick(self):
        if self._start_ts is None:
            return
        e = int(time.time() - self._start_ts)
        self._lbl_uptime.configure(
            text=f"{e//3600:02d}:{(e%3600)//60:02d}:{e%60:02d}", fg=SUCCESS)
        self._timer_id = self.after(1000, self._tick)

    def _stop_timer(self):
        self._start_ts = None
        if self._timer_id:
            self.after_cancel(self._timer_id)
            self._timer_id = None
        self._lbl_uptime.configure(text="00:00:00", fg=MUTED)


if __name__ == "__main__":
    VPNLauncher().mainloop()