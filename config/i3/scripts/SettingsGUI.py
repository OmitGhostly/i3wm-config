#!/usr/bin/env python3
"""i3wm-dots settings: mouse speed/acceleration, mouse cursor, window opacity (picom), gaps and per-monitor resolution, refresh rate, orientation.

  SettingsGUI.py            open the settings window
  SettingsGUI.py --bar-env  print the saved bar position/monitors as shell variables (used by polybar/launch.sh)
  SettingsGUI.py --apply    apply the saved settings (run at every i3 start, no GTK needed)
  SettingsGUI.py --dry-run  with --apply: print the commands instead of running them

Changes are saved to ~/.config/i3/settings.json and applied immediately with xinput / xrandr.
No root needed.  Requires: python3, python3-gobject (GTK 3), xinput, xrandr.
"""
import json
import os
import re
import shlex
import shutil
import subprocess
import sys

CONFIG_DIR = os.path.join(os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")), "i3")
SETTINGS_FILE = os.environ.get("I3DOTS_SETTINGS", os.path.join(CONFIG_DIR, "settings.json"))
ALL = "__all__"          # key used for "all mice and touchpads"
ROTATIONS = [("normal", "Landscape"), ("left", "Portrait (left)"),
             ("right", "Portrait (right)"), ("inverted", "Landscape (flipped)")]
DRY = False


# ------------------------------------------------------------------ helpers
def run(cmd, check=False):
    """Run a command list; in dry-run mode just print it."""
    if DRY:
        print("+", " ".join(shlex.quote(c) for c in cmd))
        return ""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired) as e:
        if check:
            raise
        return ""
    if check and r.returncode != 0:
        raise RuntimeError(r.stderr.strip() or "command failed: " + " ".join(cmd))
    return r.stdout


def query(cmd):
    """Read-only command, always executed (also in dry-run mode)."""
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=20).stdout
    except (OSError, subprocess.TimeoutExpired):
        return ""


def load_settings():
    try:
        with open(SETTINGS_FILE) as f:
            data = json.load(f)
    except (OSError, ValueError):
        data = {}
    if not isinstance(data, dict):
        data = {}
    # a hand-edited or damaged file must never crash the login-time apply: wrong types are dropped
    for key in ("mouse", "monitors", "opacity", "gaps", "bar", "cursor", "apps", "keybinds"):
        if key in data and not isinstance(data[key], dict):
            del data[key]
    data.setdefault("mouse", {})
    data.setdefault("monitors", {})
    return data


def save_settings(data):
    os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
    tmp = SETTINGS_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2, sort_keys=True)
        f.write("\n")
    os.replace(tmp, SETTINGS_FILE)


# ------------------------------------------------------------------ mouse
def list_pointer_devices():
    """Names of devices that expose libinput acceleration (mice, touchpads, trackballs)."""
    names = []
    for line in query(["xinput", "list", "--name-only"]).splitlines():
        name = line.strip().lstrip("↳ ").strip()
        if not name or name.startswith("Virtual core") or name in names:
            continue
        props = query(["xinput", "list-props", name])
        if "libinput Accel Speed" in props:
            names.append(name)
    return names


def apply_mouse_device(name, speed, accel):
    run(["xinput", "set-prop", name, "libinput Accel Speed", "%.2f" % speed])
    # profiles: (adaptive, flat). Acceleration off = flat.
    prof = ("1", "0") if accel else ("0", "1")
    run(["xinput", "set-prop", name, "libinput Accel Profile Enabled", prof[0], prof[1]])


def apply_mouse(settings):
    mouse = settings.get("mouse", {})
    base = mouse.get(ALL)
    for name in list_pointer_devices():
        cfg = mouse.get(name, base)
        if cfg:
            apply_mouse_device(name, float(cfg.get("speed", 0.0)), bool(cfg.get("accel", True)))


# ------------------------------------------------------------------ monitors
class Output:
    def __init__(self, name):
        self.name = name
        self.primary = False
        self.modes = {}          # "1920x1080" -> [rates as strings, highest first]
        self.cur_mode = None
        self.cur_rate = None
        self.rotate = "normal"
        self.x = 0
        self.y = 0
        self.w = 0
        self.h = 0
        self.enabled = False


def parse_xrandr(text):
    outs, cur = [], None
    for line in text.splitlines():
        m = re.match(r"^(\S+) (connected|disconnected)\b(.*)$", line)
        if m:
            cur = None
            if m.group(2) != "connected":
                continue
            cur = Output(m.group(1))
            outs.append(cur)
            rest = m.group(3)
            cur.primary = " primary" in " " + rest.split("(")[0]
            g = re.search(r"(\d+)x(\d+)\+(-?\d+)\+(-?\d+)", rest)
            if g:
                cur.enabled = True
                cur.x = int(g.group(3))
                cur.y = int(g.group(4))
                cur.w, cur.h = int(g.group(1)), int(g.group(2))
            before = rest.split("(")[0].split()
            for r in ("left", "right", "inverted"):
                if r in before:
                    cur.rotate = r
            continue
        m = re.match(r"^\s+(\d+x\d+)i?\s+(.*)$", line)
        if m and cur:
            mode, rest = m.group(1), m.group(2)
            rates = []
            for tok in rest.split():
                rm = re.match(r"^(\d+(?:\.\d+)?)([*+]*)$", tok)
                if not rm:
                    continue
                rates.append(rm.group(1))
                if "*" in rm.group(2):
                    cur.cur_mode, cur.cur_rate = mode, rm.group(1)
            if mode not in cur.modes:
                cur.modes[mode] = rates
    return outs


def mode_area(mode):
    w, h = mode.split("x")
    return int(w) * int(h)


def out_size(mode, rotate):
    """Size of a screen on the desktop (width, height) after rotation."""
    w, h = (int(v) for v in mode.split("x"))
    return (h, w) if rotate in ("left", "right") else (w, h)


def overlaps(a, b):
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return ax < bx + bw and bx < ax + aw and ay < by + bh and by < ay + ah


def touching(a, b):
    """True when two rectangles share part of an edge (no gap, no overlap)."""
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    side = (ax + aw == bx or bx + bw == ax) and ay < by + bh and by < ay + ah
    top = (ay + ah == by or by + bh == ay) and ax < bx + bw and bx < ax + aw
    return side or top


def snap_position(others, size, raw, tol=150):
    """Nearest valid spot for a screen of `size` near `raw`: glued to the edge of another screen,
    sliding freely along that edge, snapping to aligned edges / centre within `tol` pixels."""
    w, h = size
    rx, ry = raw
    if not others:
        return (rx, ry)
    cands = []
    for (ox, oy, ow, oh) in others:
        m = max(1, min(w, h, ow, oh) // 3)           # keep at least this much contact
        for x in (ox + ow, ox - w):                    # right of / left of
            y = min(max(ry, oy - h + m), oy + oh - m)
            for al in (oy, oy + oh - h, oy + (oh - h) // 2):
                if abs(y - al) <= tol:
                    y = al
                    break
            cands.append((x, y))
        for y in (oy + oh, oy - h):                    # below / above
            x = min(max(rx, ox - w + m), ox + ow - m)
            for al in (ox, ox + ow - w, ox + (ow - w) // 2):
                if abs(x - al) <= tol:
                    x = al
                    break
            cands.append((x, y))
    good = [c for c in cands if not any(overlaps((c[0], c[1], w, h), o) for o in others)]
    if not good:
        right = max(o[0] + o[2] for o in others)
        return (right, others[0][1])
    return min(good, key=lambda c: (c[0] - rx) ** 2 + (c[1] - ry) ** 2)


def build_xrandr(outputs, cfg):
    """One xrandr command that sets every output. Uses the saved x/y positions from the layout
    editor; without them the screens are laid out left to right."""
    cmd = ["xrandr"]
    enabled = [o for o in outputs if cfg.get(o.name, {}).get("enabled", True)]
    use_pos = bool(enabled) and all("x" in cfg.get(o.name, {}) and "y" in cfg.get(o.name, {}) for o in enabled)
    x = 0
    for o in sorted(outputs, key=lambda o: o.x):
        c = cfg.get(o.name, {})
        if not c.get("enabled", True):
            cmd += ["--output", o.name, "--off"]
            continue
        mode = c.get("mode")
        if mode not in o.modes:            # saved mode no longer exists on this monitor: keep what it runs now
            mode = o.cur_mode or (max(o.modes, key=mode_area) if o.modes else None)
        if not mode:
            continue
        rate = c.get("rate")
        if rate not in o.modes.get(mode, []):
            rate = o.cur_rate if mode == o.cur_mode else (o.modes[mode][0] if o.modes.get(mode) else None)
        rot = c.get("rotate", o.rotate)
        if rot not in [r for r, _ in ROTATIONS]:
            rot = o.rotate
        cmd += ["--output", o.name, "--mode", mode]
        if rate:
            cmd += ["--rate", str(rate)]
        try:
            pos = "%dx%d" % (int(c["x"]), int(c["y"])) if use_pos else "%dx0" % x
        except (KeyError, TypeError, ValueError):
            pos = "%dx0" % x
        cmd += ["--rotate", rot, "--pos", pos]
        if c.get("primary"):
            cmd += ["--primary"]
        x += out_size(mode, rot)[0]
    return cmd


def apply_monitors(settings):
    cfg = settings.get("monitors", {})
    if not cfg:
        return
    outs = parse_xrandr(query(["xrandr", "--query"]))
    outs = [o for o in outs if o.name in cfg or len(outs) == 1]
    if not outs:
        return
    cmd = build_xrandr(outs, cfg)
    if len(cmd) > 1:
        run(cmd)


def refresh_desktop(changed):
    """After a layout change: redraw the bar(s) and the wallpaper for the new screens."""
    if not changed or DRY:
        return
    for cmd in ([os.path.join(CONFIG_DIR, "scripts", "Wallpaper.sh"), "--restore"],
                [os.path.expanduser("~/.config/polybar/launch.sh")]):
        if os.path.exists(cmd[0]):
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def snapshot_monitors():
    """Current monitor state as a settings dict (used to revert a bad change)."""
    snap = {}
    for o in parse_xrandr(query(["xrandr", "--query"])):
        snap[o.name] = {"enabled": o.enabled, "mode": o.cur_mode, "rate": o.cur_rate,
                        "rotate": o.rotate, "primary": o.primary, "x": o.x, "y": o.y}
    return snap


# ------------------------------------------------------------------ mouse cursor theme
CURSOR_DEFAULT_SIZE = 24
CURSOR_SIZES = [16, 24, 32, 48, 64, 96]


def list_cursor_themes():
    """Names of installed cursor themes (icon themes that ship a cursors/ folder)."""
    dirs = [os.path.expanduser("~/.icons"), os.path.expanduser("~/.local/share/icons"),
            "/usr/share/icons", "/usr/local/share/icons"]
    dirs += [os.path.join(d, "icons") for d in os.environ.get("XDG_DATA_DIRS", "").split(":") if d]
    found = set()
    for d in dirs:
        try:
            for name in os.listdir(d):
                if os.path.isdir(os.path.join(d, name, "cursors")):
                    found.add(name)
        except OSError:
            pass
    return sorted(found, key=str.lower)


def _set_ini_key(text, key, value):
    line = "%s=%s" % (key, value)
    if re.search(r"^\s*%s\s*=.*$" % re.escape(key), text, re.M):
        return re.sub(r"^\s*%s\s*=.*$" % re.escape(key), line, text, flags=re.M)
    if "[Settings]" not in text:
        text = "[Settings]\n" + text
    return text.replace("[Settings]", "[Settings]\n" + line, 1)


def _write_if_changed(path, text):
    try:
        with open(path) as f:
            if f.read() == text:
                return
    except OSError:
        pass
    if DRY:
        print("write", path)
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(text)


def apply_cursor(settings):
    """Make the cursor theme/size the default for X apps (~/.icons/default, Xresources) and GTK apps."""
    cfg = settings.get("cursor") or {}
    theme = cfg.get("theme")
    if not theme:
        return
    if not isinstance(theme, str) or not re.match(r"^[A-Za-z0-9 ._+-]+$", theme):
        return                                         # never put anything but a plain theme name into config files
    size = max(8, min(256, int(cfg.get("size", CURSOR_DEFAULT_SIZE))))
    _write_if_changed(os.path.expanduser("~/.icons/default/index.theme"),
                      "[Icon Theme]\nName=Default\nComment=Default cursor theme\nInherits=%s\n" % theme)
    gtk = os.path.join(os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")), "gtk-3.0", "settings.ini")
    try:
        with open(gtk) as f:
            text = f.read()
    except OSError:
        text = "[Settings]\n"
    text = _set_ini_key(text, "gtk-cursor-theme-name", theme)
    text = _set_ini_key(text, "gtk-cursor-theme-size", size)
    _write_if_changed(gtk, text)
    if DRY:
        print("+ xrdb -merge  (Xcursor.theme: %s, Xcursor.size: %d)" % (theme, size))
    else:
        try:
            subprocess.run(["xrdb", "-merge"], input="Xcursor.theme: %s\nXcursor.size: %d\n" % (theme, size),
                           text=True, capture_output=True, timeout=10)
        except (OSError, subprocess.TimeoutExpired):
            pass
    run(["xsetroot", "-cursor_name", "left_ptr"])


# ------------------------------------------------------------------ window opacity (picom)
PICOM_CONF = os.path.join(os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")), "picom", "picom.conf")
OPACITY_DEFAULT = {"active": 100, "inactive": 95}


def apply_opacity(settings, restart=False):
    """Write active-opacity / inactive-opacity into picom.conf; restart picom if the file changed."""
    cfg = settings.get("opacity")
    if not cfg or not os.path.exists(PICOM_CONF):
        return
    vals = {"active-opacity": int(cfg.get("active", 100)) / 100.0,
            "inactive-opacity": int(cfg.get("inactive", 95)) / 100.0}
    with open(PICOM_CONF) as f:
        text = orig = f.read()
    for key, val in vals.items():
        line = "%s = %.2f;" % (key, val)
        if re.search(r"^\s*%s\s*=.*$" % key, text, re.M):
            text = re.sub(r"^\s*%s\s*=.*$" % key, line, text, flags=re.M)
        else:
            text += "\n" + line + "\n"
    if text == orig:
        return
    if DRY:
        print("write %s: %s" % (PICOM_CONF, ", ".join("%s=%.2f" % kv for kv in vals.items())))
        return
    with open(PICOM_CONF, "w") as f:
        f.write(text)
    if restart and subprocess.run(["pgrep", "-x", "picom"], capture_output=True).returncode == 0:
        subprocess.run(["pkill", "-x", "picom"])
        subprocess.Popen(["picom", "--config", PICOM_CONF, "-b"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


# ------------------------------------------------------------------ gaps between windows (i3)
I3_CONFIG = os.path.join(CONFIG_DIR, "config")
GAPS_DEFAULT = {"inner": 5, "outer": 0, "smart": True}


def read_value(path, key, default):
    """Current number for 'key' in a config file (first match), else the default."""
    try:
        with open(path) as f:
            m = re.search(r"^\s*%s\s*[= ]\s*([0-9.]+)" % re.escape(key), f.read(), re.M)
        return float(m.group(1)) if m else default
    except (OSError, ValueError):
        return default


def apply_gaps(settings, reload=False):
    """Write gaps inner/outer + smart_gaps into the i3 config; apply live (gaps commands, or a reload
    when smart_gaps changed, since that one is config-only)."""
    cfg = settings.get("gaps")
    if not cfg or not os.path.exists(I3_CONFIG):
        return
    inner, outer = int(cfg.get("inner", 5)), int(cfg.get("outer", 0))
    smart = "on" if cfg.get("smart", True) else "off"
    want = {"gaps inner": "gaps inner %d" % inner, "gaps outer": "gaps outer %d" % outer,
            "smart_gaps": "smart_gaps %s" % smart}
    with open(I3_CONFIG) as f:
        text = orig = f.read()
    for key, line in want.items():
        pat = r"^%s\s+.*$" % re.escape(key)
        if re.search(pat, text, re.M):
            text = re.sub(pat, line, text, count=1, flags=re.M)
        else:
            text += "\n" + line + "\n"
    if text == orig:
        return
    smart_changed = re.search(r"^smart_gaps\s+(\S+)", orig, re.M)
    smart_changed = (smart_changed.group(1) if smart_changed else None) != smart
    if DRY:
        print("write %s: %s" % (I3_CONFIG, "; ".join(want.values())))
        return
    with open(I3_CONFIG, "w") as f:
        f.write(text)
    if reload and smart_changed:
        run(["i3-msg", "reload"])
    else:
        run(["i3-msg", "gaps inner all set %d; gaps outer all set %d" % (inner, outer)])


# ------------------------------------------------------------------ top bar (polybar)
BAR_DEFAULT = {"position": "top", "monitors": None}      # monitors None = every monitor


def bar_env(settings):
    """Shell assignments for polybar/launch.sh."""
    bar = settings.get("bar") or {}
    mons = bar.get("monitors")
    lines = ["BAR_BOTTOM=%s" % ("true" if bar.get("position") == "bottom" else "false"),
             "BAR_MONITORS=%s" % shlex.quote(" ".join(mons) if mons else "")]
    return "\n".join(lines)


def apply_bar(settings):
    """Restart the bar so it picks up the new position / monitor choice."""
    launch = os.path.expanduser("~/.config/polybar/launch.sh")
    if DRY:
        print("+", launch)
        print(bar_env(settings))
    elif os.path.exists(launch):
        subprocess.Popen([launch], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


# ------------------------------------------------------------------ keybindings (i3 config)
BIND_RE = re.compile(r"^(\s*bindsym(?:\s+--\S+)*\s+)(\S+)(\s+)(.*?)\s*$")
MODE_START_RE = re.compile(r"^mode\s+.*\{\s*$")
KEYCAPTURE_MODE = "keycapture"
KEY_RE = re.compile(r"^[A-Za-z0-9_$]+(\+[A-Za-z0-9_$]+)*$")


def parse_binds(text):
    """Every top-level bindsym in the i3 config with its '## description'. id = the command (+ #n if repeated)."""
    binds, seen, desc, in_mode = [], {}, "", False
    for i, line in enumerate(text.split("\n")):
        s = line.strip()
        if MODE_START_RE.match(s):
            in_mode, desc = True, ""
            continue
        if in_mode:
            if s == "}":
                in_mode = False
            continue
        if s.startswith("## "):
            desc = s[3:]
            continue
        m = BIND_RE.match(line)
        if m:
            cmd = m.group(4)
            seen[cmd] = seen.get(cmd, 0) + 1
            bid = cmd if seen[cmd] == 1 else "%s #%d" % (cmd, seen[cmd])
            binds.append({"line": i, "key": m.group(2), "cmd": cmd, "desc": desc or cmd, "id": bid})
            desc = ""
        elif s:
            desc = ""
    return binds


def norm_key(key):
    """Canonical form for comparing key combos ($mod == Mod4, case-insensitive, any modifier order)."""
    parts = key.split("+")
    alias = {"mod4": "$mod", "mod1": "$alt", "control": "ctrl"}
    mods = sorted({alias.get(p.lower(), p.lower()) for p in parts[:-1]})
    return "+".join(mods + [parts[-1].lower()])


def pretty_key(key):
    out = []
    for p in key.split("+"):
        q = {"$mod": "Super", "mod4": "Super", "$alt": "Alt", "mod1": "Alt", "ctrl": "Ctrl", "control": "Ctrl"}.get(p.lower())
        out.append(q or (p.upper() if len(p) == 1 else p))
    return " + ".join(out)


def apply_keybinds(settings, reload=False):
    """Write the saved key overrides ({id: {"key":..., "default":...}}) into the i3 config.
    The new config is checked with `i3 -C` first; if i3 rejects it nothing is changed. Returns True if changed."""
    over = settings.get("keybinds") or {}
    if not over or not os.path.exists(I3_CONFIG):
        return False
    with open(I3_CONFIG) as f:
        text = f.read()
    lines = text.split("\n")
    binds = parse_binds(text)
    byid = {b["id"]: b for b in binds}
    used = {norm_key(b["key"]): b["id"] for b in binds}
    for bid, o in over.items():
        b = byid.get(bid)
        new = o.get("key") if isinstance(o, dict) else None
        if not b or not isinstance(new, str) or not KEY_RE.match(new) or norm_key(new) == norm_key(b["key"]):
            continue                       # (KEY_RE: nothing but a key combo can ever reach the i3 config)
        owner = used.get(norm_key(new))
        if owner and owner != bid and owner not in over:
            continue                       # another (unchanged) bind owns that combo now - leave this one alone
        lines[b["line"]] = BIND_RE.sub(lambda m: m.group(1) + new + m.group(3) + m.group(4), lines[b["line"]], count=1)
        used.pop(norm_key(b["key"]), None)
        used[norm_key(new)] = bid
        b["key"] = new
    new_text = "\n".join(lines)
    if new_text == text:
        return False
    if DRY:
        print("write %s (%d keybinding change(s))" % (I3_CONFIG, sum(1 for a, b in zip(text.split("\n"), lines) if a != b)))
        return True
    if not os.path.exists(I3_CONFIG + ".bak"):
        shutil.copy2(I3_CONFIG, I3_CONFIG + ".bak")      # one-time safety copy of the config before the first edit
    tmp = I3_CONFIG + ".new"
    with open(tmp, "w") as f:
        f.write(new_text)
    ok = True
    try:
        r = subprocess.run(["i3", "-C", "-c", tmp], capture_output=True, text=True, timeout=20)
        ok = r.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        pass                               # no i3 binary here: cannot check, write anyway
    if not ok:
        os.remove(tmp)
        raise RuntimeError("i3 rejected the new keybindings: " + (r.stderr or r.stdout).strip()[:200])
    os.replace(tmp, I3_CONFIG)
    if reload:
        run(["i3-msg", "reload"])
    return True


# ------------------------------------------------------------------ default applications (defaults.conf)
DEFAULTS_CONF = os.path.join(CONFIG_DIR, "defaults.conf")
ROFI_TERMINAL = os.path.join(CONFIG_DIR, "rofi", "00-terminal.rasi")
APP_NAMES = {
    "thunar": "Thunar", "dolphin": "Dolphin", "nautilus": "Nautilus (Files)", "nemo": "Nemo", "pcmanfm": "PCManFM",
    "pcmanfm-qt": "PCManFM-Qt", "caja": "Caja", "spacefm": "SpaceFM", "krusader": "Krusader", "doublecmd": "Double Commander",
    "ghostty": "Ghostty", "kitty": "kitty", "alacritty": "Alacritty", "wezterm": "WezTerm", "konsole": "Konsole",
    "gnome-terminal": "GNOME Terminal", "xfce4-terminal": "Xfce Terminal", "tilix": "Tilix", "terminator": "Terminator",
    "xterm": "XTerm", "st": "st", "urxvt": "rxvt-unicode", "lxterminal": "LXTerminal", "qterminal": "QTerminal",
    "firefox": "Firefox", "chromium": "Chromium", "chromium-browser": "Chromium", "google-chrome": "Google Chrome",
    "google-chrome-stable": "Google Chrome", "brave": "Brave", "brave-browser": "Brave", "vivaldi": "Vivaldi",
    "librewolf": "LibreWolf", "epiphany": "GNOME Web", "falkon": "Falkon", "qutebrowser": "qutebrowser",
    "microsoft-edge": "Microsoft Edge", "microsoft-edge-stable": "Microsoft Edge", "zen-browser": "Zen Browser",
    "floorp": "Floorp", "waterfox": "Waterfox", "opera": "Opera", "": "System default"}
# slot -> (defaults.conf key, launcher script that reads it, fallback, installable choices)
APP_SLOTS = {
    "files": {"script": "LaunchFileManager.sh", "default": "thunar", "label": "file manager",
              "choices": ["thunar", "dolphin", "nautilus", "nemo", "pcmanfm", "pcmanfm-qt", "caja", "spacefm", "krusader", "doublecmd"]},
    "term": {"script": "LaunchTerminal.sh", "default": "ghostty", "label": "terminal",
             "choices": ["ghostty", "kitty", "alacritty", "wezterm", "konsole", "gnome-terminal", "xfce4-terminal",
                         "tilix", "terminator", "lxterminal", "qterminal", "st", "urxvt", "xterm"]},
    "browser": {"script": "LaunchBrowser.sh", "default": "", "label": "browser",
                "choices": ["", "firefox", "chromium", "chromium-browser", "google-chrome", "google-chrome-stable", "brave",
                            "brave-browser", "vivaldi", "librewolf", "epiphany", "falkon", "qutebrowser", "microsoft-edge",
                            "microsoft-edge-stable", "zen-browser", "floorp", "waterfox", "opera"]},
}
SAFE_CMD = re.compile(r"^[A-Za-z0-9_./+ -]*$")      # custom commands: no quotes, $, ; | & or backticks


def app_slot_for(cmd):
    for slot, info in APP_SLOTS.items():
        if info["script"] in cmd:
            return slot
    return None


def app_name(command):
    base = command.split()[0] if command.strip() else ""
    return APP_NAMES.get(base) or (base[:1].upper() + base[1:] if base else APP_NAMES[""])


def read_defaults():
    """{'term': 'ghostty', 'files': 'thunar', ...} from defaults.conf (simple KEY="value" lines)."""
    out = {}
    try:
        with open(DEFAULTS_CONF) as f:
            for line in f:
                m = re.match(r'^\s*(\w+)=(?:"([^"]*)"|(\S*))\s*$', line)
                if m:
                    out[m.group(1)] = m.group(2) if m.group(2) is not None else m.group(3)
    except OSError:
        pass
    return out


def installed_choices(slot, current):
    """[(command, label)] for the apps from the list that are installed, plus the current one."""
    cmds = [c for c in APP_SLOTS[slot]["choices"] if c == "" or shutil.which(c)]
    if current not in cmds:
        cmds.append(current)
    seen, out = set(), []
    for c in cmds:
        label = app_name(c)
        if label in seen and c != "":        # chromium vs chromium-browser: list one
            continue
        seen.add(label)
        out.append((c, label))
    return out


def apply_apps(settings):
    """Write the chosen default apps into defaults.conf (and rofi's terminal). The launcher scripts read it."""
    apps = settings.get("apps") or {}
    if not apps or not os.path.exists(DEFAULTS_CONF):
        return False
    with open(DEFAULTS_CONF) as f:
        text = orig = f.read()
    for slot, value in apps.items():
        if slot not in APP_SLOTS or not isinstance(value, str) or not SAFE_CMD.match(value):
            continue
        line = '%s="%s"' % (slot, value)
        if re.search(r"^%s=.*$" % slot, text, re.M):
            text = re.sub(r"^%s=.*$" % slot, line, text, count=1, flags=re.M)
        else:
            text += "\n" + line + "\n"
    changed = text != orig
    if changed:
        if DRY:
            print("write %s: %s" % (DEFAULTS_CONF, ", ".join('%s="%s"' % kv for kv in apps.items())))
        else:
            with open(DEFAULTS_CONF, "w") as f:
                f.write(text)
    term = apps.get("term")
    if term and SAFE_CMD.match(term) and os.path.exists(ROFI_TERMINAL):
        with open(ROFI_TERMINAL) as f:
            rt = f.read()
        new = re.sub(r'^(\s*terminal:\s*)".*?";', lambda m: '%s"%s";' % (m.group(1), term.split()[0]), rt, count=1, flags=re.M)
        if new != rt and not DRY:
            with open(ROFI_TERMINAL, "w") as f:
                f.write(new)
    return changed


def apply_all(settings):
    """Apply every saved setting. One failing step is reported but never stops the others."""
    for step in (apply_mouse, apply_cursor, apply_monitors, apply_opacity, apply_gaps, apply_apps):
        try:
            step(settings)
        except Exception as e:  # noqa: BLE001 - login must not break on a bad setting
            print("i3 settings: %s failed: %s" % (step.__name__, e), file=sys.stderr)
    try:
        apply_keybinds(settings, reload=True)
    except Exception as e:  # noqa: BLE001
        print("i3 settings: apply_keybinds failed: %s" % e, file=sys.stderr)


# ------------------------------------------------------------------ GUI
CSS = b"""
* { font-family: "FantasqueSansM Nerd Font Mono", "Fantasque Sans Mono", monospace; font-size: 11pt;
    color: #e6e6e6; background-image: none; box-shadow: none; outline-style: none; text-shadow: none; }
*:disabled, *:insensitive { opacity: 0.4; }
treeview, treeview.view { background-color: #000000; color: #e6e6e6; }
treeview.view:selected, treeview.view:selected:focus { background-color: #ffffff; color: #000000; }
treeview header button { background-color: #1c1c1c; color: #8c8c8c; border: none; border-radius: 0; padding: 6px 10px; }
entry, searchentry { background-color: #141414; color: #e6e6e6; border: 1px solid #303030; border-radius: 0; padding: 6px 8px; }
window, dialog, box, notebook, notebook > stack, scrolledwindow, viewport { background-color: #000000; }
notebook > header { background-color: #000000; border: none; border-bottom: 1px solid #303030; }
notebook > header > tabs > tab { padding: 8px 22px; color: #6e6e6e; background-color: #000000; border: none; border-radius: 0; }
notebook > header > tabs > tab:checked { color: #000000; background-color: #ffffff; }
notebook > header > tabs > tab:checked label { color: #000000; }
frame > border { border: 1px solid #303030; border-radius: 0; }
frame > label { color: #ffffff; font-weight: bold; }
label.dim { color: #8c8c8c; }
label.title { color: #ffffff; font-size: 14pt; }
label.status { color: #8c8c8c; }
.canvas { background-color: #0a0a0a; border: 1px solid #303030; }
.mon { background-color: #303030; border: 1px solid #8c8c8c; }
.mon box, .mon-ghost box { background-color: transparent; }
.mon label { color: #e6e6e6; }
.mon .mon-num { font-size: 22pt; font-weight: bold; }
.mon .mon-name { font-size: 9pt; color: #8c8c8c; }
.mon-sel { background-color: #ffffff; border-color: #ffffff; }
.mon-sel label, .mon-sel .mon-num, .mon-sel .mon-name { color: #000000; }
.mon-ghost { background-color: rgba(255,255,255,0.18); border: 2px solid #bfbfbf; }
.ident { font-size: 72pt; font-weight: bold; color: #000000; background-color: #ffffff; padding: 10px 40px; }
button { background-color: #1c1c1c; color: #e6e6e6; border: 1px solid #303030; border-radius: 0; padding: 6px 20px; }
button:hover { background-color: #303030; }
button.suggested-action { background-color: #ffffff; color: #000000; font-weight: bold; }
button.suggested-action label { color: #000000; }
button.suggested-action:hover { background-color: #bfbfbf; }
combobox button, combobox button * { background-color: #1c1c1c; color: #e6e6e6; border-radius: 0; }
menu, menu menuitem, menu menuitem * , popover, popover * { background-color: #111111; color: #e6e6e6; border-radius: 0; }
menu menuitem:hover, menu menuitem:hover * { background-color: #ffffff; color: #000000; }
scale trough { background-color: #303030; min-height: 4px; border: none; border-radius: 0; }
scale trough highlight { background-color: #ffffff; border: none; border-radius: 0; }
scale slider { background-color: #ffffff; min-width: 14px; min-height: 14px; border-radius: 0; border: none; margin: -6px; }
scale value, scale marks, scale mark label { color: #8c8c8c; }
switch { background-color: #303030; border: 1px solid #6e6e6e; border-radius: 0; min-width: 52px; min-height: 24px; }
switch:checked { background-color: #ffffff; border-color: #ffffff; }
switch slider { background-color: #8c8c8c; border-radius: 0; border: none; min-width: 24px; min-height: 24px; margin: 0; }
switch:checked slider { background-color: #000000; }
radiobutton radio { background-color: #1c1c1c; border: 1px solid #8c8c8c; border-radius: 0; min-width: 16px; min-height: 16px; }
radiobutton radio:checked { background-color: #ffffff; border-color: #ffffff; }
scrollbar, scrollbar slider { background-color: #1c1c1c; border-radius: 0; }
"""


def launch_gui(confirm=True):
    import gi
    gi.require_version("Gtk", "3.0")
    gi.require_version("Gdk", "3.0")
    from gi.repository import Gdk, GLib, Gtk

    GLib.set_prgname("i3dots-settings")
    Gdk.set_program_class("i3dots-settings")

    provider = Gtk.CssProvider()
    provider.load_from_data(CSS)
    Gtk.StyleContext.add_provider_for_screen(
        Gdk.Screen.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    settings = load_settings()

    win = Gtk.Window(title="Settings")
    win.set_default_size(780, 600)
    win.set_position(Gtk.WindowPosition.CENTER)
    win.connect("destroy", Gtk.main_quit)

    root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
    win.add(root)
    nb = Gtk.Notebook()
    root.pack_start(nb, True, True, 0)

    def page():
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        for side in ("top", "bottom", "start", "end"):
            getattr(box, "set_margin_" + side)(22)
        return box

    def dim(text):
        lb = Gtk.Label(label=text, xalign=0)
        lb.get_style_context().add_class("dim")
        lb.set_line_wrap(True)
        return lb

    def row(label, widget, width=230):
        r = Gtk.Box(spacing=12)
        lb = Gtk.Label(label=label, xalign=0)
        lb.set_size_request(width, -1)
        r.pack_start(lb, False, False, 0)
        r.pack_start(widget, True, True, 0)
        return r

    # ---------------- mouse tab
    mp = page()
    t = Gtk.Label(label="Mouse & touchpad", xalign=0)
    t.get_style_context().add_class("title")
    mp.pack_start(t, False, False, 0)

    devices = list_pointer_devices()
    dev_combo = Gtk.ComboBoxText()
    dev_combo.append(ALL, "All mice and touchpads")
    for d in devices:
        dev_combo.append(d, d)
    dev_combo.set_active_id(ALL)
    mp.pack_start(row("Device", dev_combo), False, False, 0)

    speed = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, -1.0, 1.0, 0.05)
    speed.set_digits(2)
    speed.set_value_pos(Gtk.PositionType.RIGHT)
    speed.add_mark(0.0, Gtk.PositionType.BOTTOM, "default")
    mp.pack_start(row("Pointer speed", speed), False, False, 0)

    accel = Gtk.Switch()
    accel.set_halign(Gtk.Align.START)
    mp.pack_start(row("Mouse acceleration", accel), False, False, 0)
    mp.pack_start(dim("Acceleration off = a flat 1:1 response (the same hand movement always moves the "
                      "pointer the same distance). Speed goes from -1 (slowest) to +1 (fastest)."), False, False, 0)
    if not devices:
        mp.pack_start(dim("No mouse or touchpad with libinput settings was found. "
                          "Settings will still be saved and applied the next time a device is detected."), False, False, 0)

    # cursor theme section (same tab)
    sep = Gtk.Separator()
    mp.pack_start(sep, False, False, 6)
    ct = Gtk.Label(label="Mouse cursor", xalign=0)
    ct.get_style_context().add_class("title")
    mp.pack_start(ct, False, False, 0)
    cur_saved = settings.get("cursor", {})
    themes = list_cursor_themes()
    if cur_saved.get("theme") and cur_saved["theme"] not in themes:
        themes.append(cur_saved["theme"])
    cur_combo = Gtk.ComboBoxText()
    for th in themes:
        cur_combo.append(th, th)
    cur_combo.set_active_id(cur_saved.get("theme") or ("Adwaita" if "Adwaita" in themes else None))
    if cur_combo.get_active_id() is None and themes:
        cur_combo.set_active(0)
    mp.pack_start(row("Cursor theme", cur_combo), False, False, 0)
    cur_size = Gtk.ComboBoxText()
    for sz in CURSOR_SIZES:
        cur_size.append(str(sz), "%d px%s" % (sz, "  (default)" if sz == CURSOR_DEFAULT_SIZE else ""))
    cur_size.set_active_id(str(cur_saved.get("size", CURSOR_DEFAULT_SIZE)))
    if cur_size.get_active_id() is None:
        cur_size.set_active_id(str(CURSOR_DEFAULT_SIZE))
    mp.pack_start(row("Cursor size", cur_size), False, False, 0)
    cur_prev = Gtk.Image()
    cur_prev.set_halign(Gtk.Align.START)
    mp.pack_start(row("Preview", cur_prev), False, False, 0)
    mp.pack_start(dim("Applies to newly opened programs; apps that are already open keep their old cursor "
                      "until you restart them. More themes: install a cursor theme (for example "
                      "'bibata-cursor-theme' where your distro has it) or put one in ~/.icons."), False, False, 0)
    if not themes:
        mp.pack_start(dim("No cursor themes were found in /usr/share/icons or ~/.icons."), False, False, 0)

    def cursor_preview(*_):
        theme, size = cur_combo.get_active_id(), cur_size.get_active_id()
        if not theme or not size:
            return
        try:
            st = Gtk.Settings.get_default()
            st.set_property("gtk-cursor-theme-name", theme)
            st.set_property("gtk-cursor-theme-size", int(size))
            cur = Gdk.Cursor.new_from_name(Gdk.Display.get_default(), "left_ptr")
            pb = cur.get_image() if cur else None
            if pb is not None:
                cur_prev.set_from_pixbuf(pb)
        except Exception:  # noqa: BLE001 - the preview is optional
            pass

    cur_combo.connect("changed", cursor_preview)
    cur_size.connect("changed", cursor_preview)
    nb.append_page(mp, Gtk.Label(label="Mouse"))

    loading = {"v": False}

    def load_device(*_):
        loading["v"] = True
        cfg = settings["mouse"].get(dev_combo.get_active_id()) or settings["mouse"].get(ALL) or {}
        speed.set_value(float(cfg.get("speed", 0.0)))
        accel.set_active(bool(cfg.get("accel", True)))
        loading["v"] = False

    def store_device(*_):
        if loading["v"]:
            return
        settings["mouse"][dev_combo.get_active_id()] = {"speed": round(speed.get_value(), 2),
                                                        "accel": accel.get_active()}

    dev_combo.connect("changed", load_device)
    speed.connect("value-changed", store_device)
    accel.connect("notify::active", store_device)
    load_device()
    cursor_preview()

    # ---------------- monitors tab
    mon = page()
    t = Gtk.Label(label="Displays", xalign=0)
    t.get_style_context().add_class("title")
    mon.pack_start(t, False, False, 0)
    outputs = sorted(parse_xrandr(query(["xrandr", "--query"])), key=lambda o: (o.x, o.y))
    number = {o.name: i + 1 for i, o in enumerate(outputs)}
    saved_m = settings.get("monitors", {})
    widgets = {}
    boxes = {}
    pos = {}
    ui = {"sel": outputs[0].name if outputs else None, "drag": None}
    CW, CH = 790, 290

    mon.pack_start(dim("Drag the numbered screens to match your desk. Click one to change its settings."),
                   False, False, 0)
    canvas = Gtk.Fixed()
    canvas.set_size_request(CW, CH)
    canvas.get_style_context().add_class("canvas")
    cframe = Gtk.EventBox()
    cframe.get_style_context().add_class("canvas")
    cframe.add(canvas)
    mon.pack_start(cframe, False, False, 0)
    ghost = Gtk.Box()
    ghost.get_style_context().add_class("mon-ghost")
    canvas.put(ghost, 0, 0)

    tools = Gtk.Box(spacing=10)
    ident_btn = Gtk.Button(label="Identify")
    tools.pack_start(ident_btn, False, False, 0)
    mon.pack_start(tools, False, False, 0)

    stack = Gtk.Stack()
    mon.pack_start(stack, True, True, 0)
    primary_group = None

    def enabled_names():
        return [o.name for o in outputs if widgets[o.name][0].get_active()]

    def size_of(name):
        en, res, hz, rot, pr = widgets[name]
        m = res.get_active_id()
        return out_size(m, rot.get_active_id() or "normal") if m else (1920, 1080)

    def rect_of(name, at=None):
        x, y = at if at else pos[name]
        w, h = size_of(name)
        return (x, y, w, h)

    def settle():
        """Make the layout valid: no overlaps, every screen touching another one."""
        placed = []
        for n in enabled_names():
            r = rect_of(n)
            if placed and (any(overlaps(r, p) for p in placed) or not any(touching(r, p) for p in placed)):
                x, y = snap_position(placed, (r[2], r[3]), (r[0], r[1]))
                r = (x, y, r[2], r[3])
                pos[n] = (x, y)
            placed.append(r)

    def view_for(rects):
        if not rects:
            return 1.0, 0.0, 0.0
        x0 = min(r[0] for r in rects)
        y0 = min(r[1] for r in rects)
        x1 = max(r[0] + r[2] for r in rects)
        y1 = max(r[1] + r[3] for r in rects)
        # leave room around the layout so a screen can be dragged to any side
        world_w = (x1 - x0) + 0.9 * max(r[2] for r in rects)
        world_h = (y1 - y0) + 0.9 * max(r[3] for r in rects)
        sc = min(CW / world_w, CH / world_h)
        return sc, CW / 2 - (x0 + x1) / 2 * sc, CH / 2 - (y0 + y1) / 2 * sc

    def place_all(view=None):
        names = enabled_names()
        sc, ox, oy = view or view_for([rect_of(n) for n in names])
        ui["view"] = (sc, ox, oy)
        for o in outputs:
            b = boxes[o.name]
            if o.name in names:
                x, y, w, h = rect_of(o.name)
                b.set_size_request(max(30, int(w * sc)), max(24, int(h * sc)))
                canvas.move(b, int(ox + x * sc), int(oy + y * sc))
                b.set_opacity(1)
            else:
                # (not hide(): a widget hidden before its first layout never gets its size back)
                canvas.move(b, -5000, -5000)
                b.set_opacity(0)
            ctx = b.get_style_context()
            (ctx.add_class if o.name == ui["sel"] else ctx.remove_class)("mon-sel")
            b.sub.set_text("%s%s" % (o.name, "  ★" if widgets[o.name][4].get_active() else ""))
        canvas.move(ghost, -5000, -5000)
        ghost.set_opacity(0)

    def select(name):
        ui["sel"] = name
        stack.set_visible_child_name(name)
        place_all(ui["view"] if ui["drag"] else None)

    def on_press(box, ev, name):
        if ev.button != 1:
            return False
        select(name)
        sc, ox, oy = ui["view"]
        ui["drag"] = {"name": name, "x": ev.x_root, "y": ev.y_root, "start": pos[name], "raw": pos[name]}
        return True

    def on_motion(box, ev, name):
        d = ui["drag"]
        if not d or d["name"] != name:
            return False
        sc, ox, oy = ui["view"]
        rx = d["start"][0] + (ev.x_root - d["x"]) / sc
        ry = d["start"][1] + (ev.y_root - d["y"]) / sc
        d["raw"] = (rx, ry)
        w, h = size_of(name)
        canvas.move(box, int(ox + rx * sc), int(oy + ry * sc))
        others = [rect_of(n) for n in enabled_names() if n != name]
        gx, gy = snap_position(others, (w, h), (rx, ry))
        ghost.set_size_request(max(30, int(w * sc)), max(24, int(h * sc)))
        canvas.move(ghost, int(ox + gx * sc), int(oy + gy * sc))
        ghost.set_opacity(1)
        d["snap"] = (gx, gy)
        return True

    def on_release(box, ev, name):
        d = ui["drag"]
        ui["drag"] = None
        if d and d["name"] == name:
            if "snap" in d:
                pos[name] = (int(round(d["snap"][0])), int(round(d["snap"][1])))
            place_all()
        return True

    for o in outputs:
        sv = saved_m.get(o.name, {})
        pos[o.name] = (sv["x"], sv["y"]) if "x" in sv and "y" in sv else (o.x, o.y)

        frame = Gtk.Frame(label=" %d  -  %s " % (number[o.name], o.name))
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        for side in ("top", "bottom", "start", "end"):
            getattr(box, "set_margin_" + side)(14)
        frame.add(box)

        en = Gtk.Switch()
        en.set_halign(Gtk.Align.START)
        en.set_active(sv.get("enabled", o.enabled))
        box.pack_start(row("Enabled", en, 150), False, False, 0)

        res = Gtk.ComboBoxText()
        for m in sorted(o.modes, key=mode_area, reverse=True):
            res.append(m, m.replace("x", " × "))
        want_mode = sv.get("mode") or o.cur_mode or (max(o.modes, key=mode_area) if o.modes else None)
        res.set_active_id(want_mode)
        box.pack_start(row("Resolution", res, 150), False, False, 0)

        hz = Gtk.ComboBoxText()
        box.pack_start(row("Refresh rate", hz, 150), False, False, 0)

        def make_fill(res, hz, o):
            def fill(want=None):
                hz.remove_all()
                for r in o.modes.get(res.get_active_id() or "", []):
                    hz.append(r, "%s Hz" % r)
                if not (want and hz.set_active_id(want)):
                    hz.set_active(0)
            return fill
        fill = make_fill(res, hz, o)
        fill(sv.get("rate") or o.cur_rate)
        res.connect("changed", lambda *_a, f=fill: f(None))

        rot = Gtk.ComboBoxText()
        for key, label in ROTATIONS:
            rot.append(key, label)
        rot.set_active_id(sv.get("rotate", o.rotate))
        box.pack_start(row("Orientation", rot, 150), False, False, 0)

        pr = Gtk.RadioButton.new_with_label_from_widget(primary_group, "Make this the primary display")
        if primary_group is None:
            primary_group = pr
        pr.set_active(sv.get("primary", o.primary))
        box.pack_start(row("", pr, 150), False, False, 0)

        widgets[o.name] = (en, res, hz, rot, pr)
        stack.add_named(frame, o.name)

        eb = Gtk.EventBox()
        eb.get_style_context().add_class("mon")
        eb.add_events(Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.BUTTON_RELEASE_MASK |
                      Gdk.EventMask.POINTER_MOTION_MASK)
        vb = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        vb.set_valign(Gtk.Align.CENTER)
        num = Gtk.Label(label=str(number[o.name]))
        num.get_style_context().add_class("mon-num")
        eb.sub = Gtk.Label(label=o.name)
        eb.sub.get_style_context().add_class("mon-name")
        vb.pack_start(num, False, False, 0)
        vb.pack_start(eb.sub, False, False, 0)
        eb.add(vb)
        eb.connect("button-press-event", on_press, o.name)
        eb.connect("motion-notify-event", on_motion, o.name)
        eb.connect("button-release-event", on_release, o.name)
        canvas.put(eb, 0, 0)
        boxes[o.name] = eb

        def changed(*_a):
            settle()
            place_all()
        en.connect("notify::active", changed)
        res.connect("changed", changed)
        rot.connect("changed", changed)
        pr.connect("toggled", changed)

    canvas.remove(ghost)          # re-add last so the drop preview is drawn above the screens
    canvas.put(ghost, 0, 0)
    if not outputs:
        mon.pack_start(dim("No displays were detected (xrandr found nothing)."), False, False, 0)
    else:
        settle()
        stack.set_visible_child_name(ui["sel"])
    mon.pack_start(dim("After applying, you get 10 seconds to confirm - if the screen goes dark, "
                       "just wait and it reverts."), False, False, 0)
    nb.append_page(mon, Gtk.Label(label="Displays"))

    # ---------------- appearance tab
    ap = page()
    t = Gtk.Label(label="Window opacity", xalign=0)
    t.get_style_context().add_class("title")
    ap.pack_start(t, False, False, 0)
    op = settings.get("opacity") or {
        "active": round(read_value(PICOM_CONF, "active-opacity", 1.0) * 100),
        "inactive": round(read_value(PICOM_CONF, "inactive-opacity", 0.95) * 100)}

    def pct_scale(value):
        sc = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 20, 100, 1)
        sc.set_digits(0)
        sc.set_value_pos(Gtk.PositionType.RIGHT)
        sc.set_value(value)
        sc.connect("format-value", lambda _s, v: "%d%%" % v)
        return sc

    op_active = pct_scale(op.get("active", OPACITY_DEFAULT["active"]))
    op_inactive = pct_scale(op.get("inactive", OPACITY_DEFAULT["inactive"]))
    ap.pack_start(row("Focused window", op_active), False, False, 0)
    ap.pack_start(row("Unfocused windows", op_inactive), False, False, 0)
    ap.pack_start(dim("100% is fully solid; lower is more see-through. Set the unfocused value lower than the "
                      "focused one to make the window you are using stand out. Needs the compositor (picom) "
                      "to be running. Video players and fullscreen windows stay solid."), False, False, 0)

    # gaps section (same tab)
    mp_sep = Gtk.Separator()
    ap.pack_start(mp_sep, False, False, 6)
    gt = Gtk.Label(label="Gaps between windows", xalign=0)
    gt.get_style_context().add_class("title")
    ap.pack_start(gt, False, False, 0)
    gp = settings.get("gaps") or {
        "inner": int(read_value(I3_CONFIG, "gaps inner", GAPS_DEFAULT["inner"])),
        "outer": int(read_value(I3_CONFIG, "gaps outer", GAPS_DEFAULT["outer"])),
        "smart": not re.search(r"^\s*smart_gaps\s+off", open(I3_CONFIG).read(), re.M) if os.path.exists(I3_CONFIG) else True}

    def px_scale(value):
        sc = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 40, 1)
        sc.set_digits(0)
        sc.set_value_pos(Gtk.PositionType.RIGHT)
        sc.set_value(value)
        sc.connect("format-value", lambda _s, v: "%d px" % v)
        return sc

    gap_inner = px_scale(gp.get("inner", GAPS_DEFAULT["inner"]))
    gap_outer = px_scale(gp.get("outer", GAPS_DEFAULT["outer"]))
    gap_smart = Gtk.Switch()
    gap_smart.set_halign(Gtk.Align.START)
    gap_smart.set_active(bool(gp.get("smart", GAPS_DEFAULT["smart"])))
    ap.pack_start(row("Between windows", gap_inner), False, False, 0)
    ap.pack_start(row("Around the screen edge", gap_outer), False, False, 0)
    ap.pack_start(row("No gaps for a lone window", gap_smart), False, False, 0)
    ap.pack_start(dim("0 px = windows touch (no gap). Turning the last option on makes a single window "
                      "fill the screen. Changing it reloads i3 (your windows stay open)."), False, False, 0)

    # top bar section (same tab)
    ap.pack_start(Gtk.Separator(), False, False, 6)
    bt = Gtk.Label(label="Bar", xalign=0)
    bt.get_style_context().add_class("title")
    ap.pack_start(bt, False, False, 0)
    bar_saved = settings.get("bar", {})
    bar_pos = Gtk.ComboBoxText()
    bar_pos.append("top", "Top of the screen")
    bar_pos.append("bottom", "Bottom of the screen")
    bar_pos.set_active_id(bar_saved.get("position", "top") if bar_saved.get("position") in ("top", "bottom") else "top")
    ap.pack_start(row("Bar position", bar_pos), False, False, 0)
    bar_all = Gtk.Switch()
    bar_all.set_halign(Gtk.Align.START)
    bar_sel = bar_saved.get("monitors")
    bar_all.set_active(not bar_sel)
    ap.pack_start(row("Show on all monitors", bar_all), False, False, 0)
    bar_checks = {}
    bar_list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
    for o in sorted(parse_xrandr(query(["xrandr", "--query"])), key=lambda o: (o.x, o.y)):
        if not o.enabled:
            continue
        cb = Gtk.CheckButton(label="%d  -  %s%s" % (len(bar_checks) + 1, o.name, "  (primary)" if o.primary else ""))
        cb.set_active(not bar_sel or o.name in bar_sel)
        bar_checks[o.name] = cb
        bar_list.pack_start(cb, False, False, 0)
    bar_list_row = row("Show only on", bar_list)
    ap.pack_start(bar_list_row, False, False, 0)
    ap.pack_start(dim("The numbers match the screens in the Displays tab. The system tray goes on the primary "
                      "monitor if it shows the bar, otherwise on the first one that does. Left and right "
                      "positions are not available: the bar program (polybar) can only sit on the top or bottom."),
                  False, False, 0)

    def bar_toggle(*_):
        bar_list_row.set_sensitive(not bar_all.get_active() and bool(bar_checks))
    bar_all.connect("notify::active", bar_toggle)
    bar_toggle()
    ap_scroll = Gtk.ScrolledWindow()
    ap_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
    ap_scroll.add(ap)
    nb.append_page(ap_scroll, Gtk.Label(label="Appearance"))

    # ---------------- keybindings tab
    kp = page()
    t = Gtk.Label(label="Keybindings", xalign=0)
    t.get_style_context().add_class("title")
    kp.pack_start(t, False, False, 0)
    kp.pack_start(dim("Pick a row, then Change key and press the new combination. Super is the key with the "
                      "Windows/logo symbol. Changes are written to your i3 config when you press Apply."),
                  False, False, 0)
    kb_search = Gtk.SearchEntry()
    kb_search.set_placeholder_text("Search by action or key...")
    kp.pack_start(kb_search, False, False, 0)

    try:
        with open(I3_CONFIG) as f:
            kb_binds = parse_binds(f.read())
    except OSError:
        kb_binds = []
    kb_over = dict(settings.get("keybinds") or {})
    kb_default = {b["id"]: kb_over.get(b["id"], {}).get("default", b["key"]) for b in kb_binds}
    kb_cur = {b["id"]: b["key"] for b in kb_binds}          # what the config says now
    kb_new = dict(kb_cur)                                    # what the list shows (edited, not yet applied)
    saved_apps = settings.get("apps") or {}
    defaults_now = read_defaults()
    app_new = {slot: saved_apps.get(slot, defaults_now.get(slot, info["default"])) for slot, info in APP_SLOTS.items()}
    kb_slot = {b["id"]: app_slot_for(b["cmd"]) for b in kb_binds}

    def kb_label(bid):
        desc = next((b["desc"] for b in kb_binds if b["id"] == bid), bid)
        slot = kb_slot.get(bid)
        return "%s (%s)" % (desc, app_name(app_new[slot])) if slot else desc

    kb_store = Gtk.ListStore(str, str, str, str)             # label, keys, id, weight marker
    for b in kb_binds:
        kb_store.append([kb_label(b["id"]), pretty_key(b["key"]), b["id"], ""])
    kb_filter = kb_store.filter_new()

    def kb_visible(model, it, _data=None):
        q = kb_search.get_text().strip().lower()
        return not q or q in model[it][0].lower() or q in model[it][1].lower()
    kb_filter.set_visible_func(kb_visible)
    kb_view = Gtk.TreeView(model=kb_filter)
    kb_view.set_headers_visible(True)
    for title, col, expand in (("Action", 0, True), ("Keys", 1, False)):
        cell = Gtk.CellRendererText()
        cell.set_property("ellipsize", 3)
        tc = Gtk.TreeViewColumn(title, cell, text=col)
        tc.set_expand(expand)
        tc.set_resizable(True)
        if col == 1:
            tc.set_min_width(300)
        tc.set_cell_data_func(cell, lambda _c, rend, model, it, col=col: rend.set_property(
            "weight", 700 if model[it][3] else 400) or rend.set_property("text", model[it][col] + (" *" if col == 1 and model[it][3] else "")))
        kb_view.append_column(tc)
    kb_scroll = Gtk.ScrolledWindow()
    kb_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
    kb_scroll.set_min_content_height(470)
    kb_scroll.add(kb_view)
    kp.pack_start(kb_scroll, True, True, 0)
    kb_btns = Gtk.Box(spacing=10)
    kb_change = Gtk.Button(label="Change key...")
    kb_reset = Gtk.Button(label="Reset this one")
    kb_reset_all = Gtk.Button(label="Reset all to default")
    kb_app = Gtk.Button(label="Change application...")
    kb_app.set_sensitive(False)
    for b_ in (kb_change, kb_app, kb_reset, kb_reset_all):
        kb_btns.pack_start(b_, False, False, 0)
    kp.pack_start(kb_btns, False, False, 0)
    kp.pack_start(dim("Rows with an application in brackets, like the file manager, terminal and browser, also have "
                      "Change application... to pick which program that key opens."), False, False, 0)
    nb.append_page(kp, Gtk.Label(label="Keybindings"))

    def kb_selected_id():
        model, it = kb_view.get_selection().get_selected()
        return model[it][2] if it else None

    def kb_refresh_row(bid):
        for row_ in kb_store:
            if row_[2] == bid:
                row_[0] = kb_label(bid)
                row_[1] = pretty_key(kb_new[bid])
                row_[3] = "*" if norm_key(kb_new[bid]) != norm_key(kb_default[bid]) else ""
        kb_filter.refilter()

    def kb_desc(bid):
        return next((b["desc"] for b in kb_binds if b["id"] == bid), bid)

    modifier_keys = {"Shift_L", "Shift_R", "Control_L", "Control_R", "Alt_L", "Alt_R", "Super_L", "Super_R",
                     "Meta_L", "Meta_R", "Hyper_L", "Hyper_R", "ISO_Level3_Shift", "Caps_Lock", "Num_Lock",
                     "Mode_switch"}

    def capture_key(bid):
        """Dialog that records one key combination. Returns the i3 key string, or None."""
        have_mode = ('mode "%s"' % KEYCAPTURE_MODE) in open(I3_CONFIG).read()
        if have_mode and not DRY:
            # i3 normally swallows bound combos (even Super+Return); switch to a mode with no bindings meanwhile
            run(["i3-msg", 'mode "%s"' % KEYCAPTURE_MODE])
            subprocess.Popen(["sh", "-c", "sleep 90; i3-msg -t get_binding_state | grep -q %s && i3-msg mode default"
                              % KEYCAPTURE_MODE], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        dlg = Gtk.Dialog(title="Change key", transient_for=win, modal=True)
        dlg.set_default_size(460, 190)
        area = dlg.get_content_area()
        area.set_spacing(14)
        for side in ("top", "bottom", "start", "end"):
            getattr(area, "set_margin_" + side)(18)
        area.pack_start(Gtk.Label(label=kb_desc(bid), xalign=0), False, False, 0)
        shown = Gtk.Label(label="Press the new key combination...")
        shown.get_style_context().add_class("title")
        area.pack_start(shown, True, True, 0)
        hint = dim("Hold the modifiers (Super, Alt, Ctrl, Shift), then press a key.")
        area.pack_start(hint, False, False, 0)
        dlg.add_button("Cancel", Gtk.ResponseType.CANCEL)
        ok_btn = dlg.add_button("Set", Gtk.ResponseType.OK)
        ok_btn.set_sensitive(False)
        got = {"key": None}

        def on_key(_w, ev):
            name = Gdk.keyval_name(ev.keyval) or ""
            if name in modifier_keys:
                return True
            keymap = Gdk.Keymap.get_for_display(Gdk.Display.get_default())
            found, base, _grp, _lvl, _cons = keymap.translate_keyboard_state(
                ev.hardware_keycode, Gdk.ModifierType(0), ev.group)
            key = Gdk.keyval_name(Gdk.keyval_to_lower(base if found else ev.keyval)) or name
            st = ev.state
            mods = []
            if st & (Gdk.ModifierType.SUPER_MASK | Gdk.ModifierType.MOD4_MASK):
                mods.append("$mod")
            if st & Gdk.ModifierType.MOD1_MASK:
                mods.append("$alt")
            if st & Gdk.ModifierType.CONTROL_MASK:
                mods.append("Ctrl")
            if st & Gdk.ModifierType.SHIFT_MASK:
                mods.append("Shift")
            special = key.startswith(("XF86", "F")) and (key.startswith("XF86") or key[1:].isdigit()) or key in ("Print", "Pause")
            if not mods and not special:
                shown.set_text("Add a modifier (Super, Alt or Ctrl)")
                ok_btn.set_sensitive(False)
                got["key"] = None
                return True
            got["key"] = "+".join(mods + [key])
            shown.set_text(pretty_key(got["key"]))
            ok_btn.set_sensitive(True)
            return True
        dlg.connect("key-press-event", on_key)
        dlg.show_all()
        try:
            resp = dlg.run()
        finally:
            dlg.destroy()
            if have_mode and not DRY:
                run(["i3-msg", "mode default"])
        return got["key"] if resp == Gtk.ResponseType.OK else None

    def kb_change_key(*_):
        bid = kb_selected_id()
        if not bid:
            status.set_text("Pick an action first.")
            return
        new = capture_key(bid)
        if not new:
            return
        clash = next((o for o in kb_new if o != bid and norm_key(kb_new[o]) == norm_key(new)), None)
        if clash:
            d = Gtk.MessageDialog(transient_for=win, modal=True, message_type=Gtk.MessageType.QUESTION,
                                  buttons=Gtk.ButtonsType.NONE, text="%s is already used" % pretty_key(new))
            d.format_secondary_text('It belongs to "%s". Swap the two keys?' % kb_desc(clash))
            d.add_button("Cancel", Gtk.ResponseType.CANCEL)
            d.add_button("Swap", Gtk.ResponseType.YES)
            resp = d.run()
            d.destroy()
            if resp != Gtk.ResponseType.YES:
                return
            kb_new[clash] = kb_new[bid]
            kb_refresh_row(clash)
        kb_new[bid] = new
        kb_refresh_row(bid)
        status.set_text("Press Apply to save the new keybindings.")

    def kb_reset_one(*_):
        bid = kb_selected_id()
        if not bid:
            return
        want = kb_default[bid]
        clash = next((o for o in kb_new if o != bid and norm_key(kb_new[o]) == norm_key(want)), None)
        if clash:
            kb_new[clash] = kb_new[bid]
            kb_refresh_row(clash)
        kb_new[bid] = want
        kb_refresh_row(bid)

    def kb_reset_everything(*_):
        for bid in kb_new:
            kb_new[bid] = kb_default[bid]
            kb_refresh_row(bid)

    def kb_update_buttons(*_):
        bid = kb_selected_id()
        kb_app.set_sensitive(bool(bid and kb_slot.get(bid)))

    def kb_change_app(*_):
        bid = kb_selected_id()
        slot = kb_slot.get(bid) if bid else None
        if not slot:
            return
        info = APP_SLOTS[slot]
        dlg = Gtk.Dialog(title="Change %s" % info["label"], transient_for=win, modal=True)
        area = dlg.get_content_area()
        area.set_spacing(12)
        for side in ("top", "bottom", "start", "end"):
            getattr(area, "set_margin_" + side)(18)
        area.pack_start(Gtk.Label(label="Which program should %s open?" % pretty_key(kb_new[bid]), xalign=0), False, False, 0)
        combo = Gtk.ComboBoxText()
        for cmd, label in installed_choices(slot, app_new[slot]):
            combo.append(cmd or "__default__", "%s%s" % (label, "  (%s)" % cmd if cmd else ""))
        combo.append("__other__", "Other... (type a command)")
        cur = app_new[slot]
        combo.set_active_id(cur or "__default__")
        area.pack_start(combo, False, False, 0)
        entry = Gtk.Entry()
        entry.set_placeholder_text("command, e.g. mybrowser --private-window")
        entry.set_no_show_all(True)
        area.pack_start(entry, False, False, 0)
        note = dim("Only programs found on this computer are listed. Other opens any command you type.")
        area.pack_start(note, False, False, 0)
        err = dim("")
        area.pack_start(err, False, False, 0)
        dlg.add_button("Cancel", Gtk.ResponseType.CANCEL)
        dlg.add_button("Set", Gtk.ResponseType.OK)

        def on_combo(*_a):
            entry.set_visible(combo.get_active_id() == "__other__")
        combo.connect("changed", on_combo)
        dlg.show_all()
        on_combo()
        chosen = None
        while True:
            if dlg.run() != Gtk.ResponseType.OK:
                break
            pick = combo.get_active_id()
            val = entry.get_text().strip() if pick == "__other__" else ("" if pick == "__default__" else pick)
            if pick == "__other__" and (not val or not SAFE_CMD.match(val)):
                err.set_text("Use only letters, numbers, spaces and . _ / + - in the command.")
                continue
            chosen = val
            break
        dlg.destroy()
        if chosen is None:
            return
        app_new[slot] = chosen
        for b_id, sl in kb_slot.items():
            if sl == slot:
                kb_refresh_row(b_id)
        status.set_text("Press Apply to save: %s -> %s" % (info["label"], app_name(chosen)))

    kb_view.get_selection().connect("changed", kb_update_buttons)
    kb_app.connect("clicked", kb_change_app)
    kb_change.connect("clicked", kb_change_key)
    kb_reset.connect("clicked", kb_reset_one)
    kb_reset_all.connect("clicked", kb_reset_everything)
    kb_view.connect("row-activated", kb_change_key)
    kb_search.connect("search-changed", lambda *_: kb_filter.refilter())

    def kb_commit():
        """Turn the edited list into saved overrides and write them to the i3 config."""
        over = {}
        for bid, key in kb_new.items():
            if norm_key(key) != norm_key(kb_default[bid]):
                over[bid] = {"key": key, "default": kb_default[bid]}
        settings["keybinds"] = over
        # a key that went back to its default must also be written back
        for bid, key in kb_new.items():
            if bid not in over and norm_key(kb_cur[bid]) != norm_key(key):
                over[bid] = {"key": key, "default": kb_default[bid]}
        changed = apply_keybinds(settings, reload=True)
        settings["keybinds"] = {b: o for b, o in over.items() if norm_key(o["key"]) != norm_key(kb_default[b])}
        for bid in kb_new:
            kb_cur[bid] = kb_new[bid]
        return changed

    def identify(*_):
        """Flash each screen's number on that screen for a moment."""
        for o in parse_xrandr(query(["xrandr", "--query"])):
            if not o.enabled:
                continue
            w = Gtk.Window(type=Gtk.WindowType.POPUP)
            w.set_default_size(150, 150)
            w.move(o.x + 40, o.y + 60)
            lb = Gtk.Label(label=str(number.get(o.name, "?")))
            lb.get_style_context().add_class("ident")
            w.add(lb)
            w.show_all()
            GLib.timeout_add_seconds(3, lambda w=w: (w.destroy(), False)[1])
    ident_btn.connect("clicked", identify)

    # ---------------- buttons
    bar = Gtk.Box(spacing=10)
    for side in ("top", "bottom", "start", "end"):
        getattr(bar, "set_margin_" + side)(14)
    status = Gtk.Label(label="", xalign=0)
    status.get_style_context().add_class("status")
    bar.pack_start(status, True, True, 0)
    close = Gtk.Button(label="Close")
    close.connect("clicked", lambda *_: win.destroy())
    apply_btn = Gtk.Button(label="Apply")
    apply_btn.get_style_context().add_class("suggested-action")
    bar.pack_end(apply_btn, False, False, 0)
    bar.pack_end(close, False, False, 0)
    root.pack_start(bar, False, False, 0)

    def collect_monitors():
        cfg = {}
        names = enabled_names()
        x0 = min([pos[n][0] for n in names] or [0])
        y0 = min([pos[n][1] for n in names] or [0])
        for name, (en, res, hz, rot, pr) in widgets.items():
            px, py = pos[name] if name in names else (x0, y0)
            cfg[name] = {"enabled": en.get_active(), "mode": res.get_active_id(),
                         "rate": hz.get_active_id(), "rotate": rot.get_active_id(),
                         "primary": pr.get_active(), "x": int(px - x0), "y": int(py - y0)}
        return cfg

    def ask_keep():
        d = Gtk.MessageDialog(transient_for=win, modal=True, message_type=Gtk.MessageType.QUESTION,
                              buttons=Gtk.ButtonsType.NONE, text="Keep these display settings?")
        d.add_button("Revert", Gtk.ResponseType.NO)
        d.add_button("Keep", Gtk.ResponseType.YES)
        left = {"n": 10}
        d.format_secondary_text("Reverting in %d seconds..." % left["n"])

        def tick():
            left["n"] -= 1
            if left["n"] <= 0:
                d.response(Gtk.ResponseType.NO)
                return False
            d.format_secondary_text("Reverting in %d seconds..." % left["n"])
            return True
        tid = GLib.timeout_add_seconds(1, tick)
        resp = d.run()
        GLib.source_remove(tid) if left["n"] > 0 else None
        d.destroy()
        return resp == Gtk.ResponseType.YES

    def on_apply(*_):
        try:
            apply_everything()
        except Exception as e:  # noqa: BLE001 - never let a failed apply crash the window
            status.set_text("Error: %s" % e)

    def apply_everything():
        store_device()
        if cur_combo.get_active_id():
            settings["cursor"] = {"theme": cur_combo.get_active_id(), "size": int(cur_size.get_active_id())}
            apply_cursor(settings)
        settings["opacity"] = {"active": int(op_active.get_value()), "inactive": int(op_inactive.get_value())}
        apply_opacity(settings, restart=True)
        settings["gaps"] = {"inner": int(gap_inner.get_value()), "outer": int(gap_outer.get_value()),
                            "smart": gap_smart.get_active()}
        apply_gaps(settings, reload=True)
        settings["apps"] = dict(app_new)
        apply_apps(settings)
        kb_commit()
        chosen = [n for n, cb in bar_checks.items() if cb.get_active()]
        if bar_all.get_active() or not chosen:
            chosen = None
            if not bar_all.get_active():
                bar_all.set_active(True)      # nothing ticked = show everywhere, never a bar-less desktop
        old_bar = settings.get("bar") or {}
        settings["bar"] = {"position": bar_pos.get_active_id() or "top", "monitors": chosen}
        if settings["bar"] != {"position": old_bar.get("position", "top"), "monitors": old_bar.get("monitors")}:
            apply_bar(settings)       # only restart the bar when its settings actually changed
        before = snapshot_monitors()
        new_mon = collect_monitors() if widgets else {}
        settings["monitors"] = new_mon or settings.get("monitors", {})
        try:
            apply_mouse(settings)
            changed = bool(new_mon) and new_mon != {k: v for k, v in before.items() if k in new_mon}
            if new_mon:
                apply_monitors(settings)
                refresh_desktop(changed)
            if changed and confirm and not DRY and not ask_keep():
                settings["monitors"] = before
                apply_monitors(settings)
                for name, (en, res, hz, rot, pr) in widgets.items():
                    b = before.get(name, {})
                    if b.get("mode"):
                        res.set_active_id(b["mode"])
                        hz.set_active_id(b.get("rate"))
                    rot.set_active_id(b.get("rotate", "normal"))
                    en.set_active(b.get("enabled", True))
                    pr.set_active(b.get("primary", False))
                    if "x" in b:
                        pos[name] = (b["x"], b["y"])
                settle()
                place_all()
                status.set_text("Reverted the display change.")
                save_settings(settings)
                return
            save_settings(settings)
            status.set_text("Saved to %s" % SETTINGS_FILE.replace(os.path.expanduser("~"), "~"))
        except Exception as e:  # noqa: BLE001 - show any failure to the user
            status.set_text("Error: %s" % e)

    apply_btn.connect("clicked", on_apply)
    win.show_all()
    if outputs:
        place_all()
    Gtk.main()


def main(argv):
    global DRY
    DRY = "--dry-run" in argv
    if "--bar-env" in argv:
        print(bar_env(load_settings()))
        return 0
    if "--apply" in argv:
        apply_all(load_settings())
        return 0
    if "--help" in argv or "-h" in argv:
        print(__doc__)
        return 0
    try:
        launch_gui(confirm="--no-confirm" not in argv)
    except ImportError:
        # `python3` may be a pyenv/conda/venv one without GTK: retry with the system Python that has it
        if not os.environ.get("I3DOTS_REEXEC"):
            import glob
            check = "import gi; gi.require_version('Gtk', '3.0'); from gi.repository import Gtk"
            cands = ["/usr/bin/python3"] + sorted(glob.glob("/usr/bin/python3.*[0-9]"), reverse=True)
            for cand in cands:
                if os.path.exists(cand) and os.path.realpath(cand) != os.path.realpath(sys.executable):
                    if subprocess.run([cand, "-c", check], capture_output=True).returncode == 0:
                        os.environ["I3DOTS_REEXEC"] = "1"
                        os.execv(cand, [cand] + sys.argv)
        print("The settings window needs GTK for Python. Install it:\n"
              "  Fedora:  sudo dnf install python3-gobject gtk3\n"
              "  Arch:    sudo pacman -S python-gobject gtk3\n"
              "  Debian:  sudo apt install python3-gi gir1.2-gtk-3.0", file=sys.stderr)
        os.system("notify-send 'Settings' 'Install python3-gobject (GTK) to use the settings window' 2>/dev/null")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
