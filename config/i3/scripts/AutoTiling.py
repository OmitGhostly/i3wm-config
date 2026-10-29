#!/usr/bin/env python3
"""Spiral ("dwindle") tiling for i3, the way Hyprland tiles by default.

Whenever a window gets focus, i3 is told to split it along its longer side: a wide window is split side by
side, a tall one top and bottom. Opening windows one after another fills the screen like Hyprland:

    [ 1 ]  ->  [ 1 | 2 ]  ->  [ 1 | 2 ]  ->  [ 1 |  2  ]
                              [   | 3 ]      [   | 3|4 ]

Tabbed / stacked containers (SUPER+ALT+2/3), floating and fullscreen windows are left alone.
Turn it on or off with SUPER+ALT+T, or in Settings > Appearance > Window tiling.
Needs nothing but python3: it talks to i3's IPC socket directly.

  AutoTiling.py            run (started by the i3 config; only one copy ever runs)
  AutoTiling.py --toggle   switch between spiral and classic (side by side) tiling
  AutoTiling.py --status   print the current mode
"""
import fcntl
import json
import os
import socket
import struct
import subprocess
import sys
import time

MAGIC = b"i3-ipc"
RUN_COMMAND, SUBSCRIBE, GET_TREE = 0, 2, 4
EVENT_BIT = 1 << 31
MODES = ("dwindle", "classic")          # dwindle = Hyprland-style spiral, classic = plain i3 (side by side)
DEFAULT_MODE = "dwindle"
CONFIG_DIR = os.path.join(os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config"), "i3")
SETTINGS = os.environ.get("I3DOTS_SETTINGS") or os.path.join(CONFIG_DIR, "settings.json")
RECONNECT_FOR = 30                       # seconds to wait for i3 to come back (in-place restart) before exiting


# ------------------------------------------------------------------ mode (stored in settings.json)
def _load():
    try:
        with open(SETTINGS) as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


_cache = {"mtime": None, "mode": DEFAULT_MODE}


def read_mode():
    """The saved mode; re-read only when settings.json changed (cheap to call on every event)."""
    try:
        mtime = os.stat(SETTINGS).st_mtime_ns
    except OSError:
        mtime = None
    if mtime != _cache["mtime"]:
        t = _load().get("tiling")
        mode = t.get("mode") if isinstance(t, dict) else None
        _cache.update(mtime=mtime, mode=mode if mode in MODES else DEFAULT_MODE)
    return _cache["mode"]


def save_mode(mode):
    data = _load()
    data["tiling"] = {"mode": mode}
    os.makedirs(os.path.dirname(SETTINGS), exist_ok=True)
    tmp = SETTINGS + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2, sort_keys=True)
        f.write("\n")
    os.replace(tmp, SETTINGS)


def notify(text):
    try:
        subprocess.run(["notify-send", "-u", "low", "Window tiling", text], capture_output=True, timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        pass


# ------------------------------------------------------------------ i3 IPC
def socket_path():
    path = os.environ.get("I3SOCK")
    if path and os.path.exists(path):
        return path
    try:
        return subprocess.run(["i3", "--get-socketpath"], capture_output=True, text=True, timeout=5).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return ""


class IPC:
    def __init__(self, path):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.connect(path)

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass

    def _read(self, n):
        buf = b""
        while len(buf) < n:
            chunk = self.sock.recv(n - len(buf))
            if not chunk:
                raise ConnectionError("i3 closed the connection")
            buf += chunk
        return buf

    def send(self, mtype, payload=""):
        body = payload.encode()
        self.sock.sendall(MAGIC + struct.pack("=II", len(body), mtype) + body)

    def recv(self):
        head = self._read(14)
        if head[:6] != MAGIC:
            raise ConnectionError("not an i3 IPC reply")
        length, mtype = struct.unpack("=II", head[6:])
        return mtype, json.loads(self._read(length) or b"null")

    def request(self, mtype, payload=""):
        self.send(mtype, payload)
        while True:
            t, data = self.recv()
            if not t & EVENT_BIT:          # (this socket is not subscribed, but never mistake an event for the reply)
                return data


def find_focused(node, parent=None):
    if node.get("focused"):
        return node, parent
    for child in node.get("nodes", []) + node.get("floating_nodes", []):
        hit = find_focused(child, node)
        if hit:
            return hit
    return None


def retile(cmd):
    """Set the split direction of the focused window to its longer side (what Hyprland's dwindle does)."""
    if read_mode() != "dwindle":
        return
    hit = find_focused(cmd.request(GET_TREE))
    if not hit:
        return
    con, parent = hit
    if con.get("type") != "con" or not con.get("window") or parent is None:
        return                                          # an empty workspace, or not a real window
    if parent.get("type") == "floating_con" or str(con.get("floating", "")).endswith("_on"):
        return                                          # floating windows are placed by hand
    if con.get("fullscreen_mode") or parent.get("layout") in ("tabbed", "stacked"):
        return                                          # keep tabs / stacks the user asked for
    rect = con.get("rect") or {}
    width, height = rect.get("width", 0), rect.get("height", 0)
    if not width or not height:
        return
    want = "splitv" if height > width else "splith"
    if parent.get("layout") != want:
        cmd.request(RUN_COMMAND, "split vertical" if want == "splitv" else "split horizontal")


def run():
    lock_dir = os.environ.get("XDG_RUNTIME_DIR") or "/tmp"
    lock = open(os.path.join(lock_dir, "i3dots-autotiling-%d.lock" % os.getuid()), "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return 0                                        # already running (i3 reload starts it again)
    last_ok = time.monotonic()
    while True:
        events = cmd = None
        try:
            path = socket_path()
            if not path:
                raise ConnectionError("i3 is not running")
            events, cmd = IPC(path), IPC(path)
            events.send(SUBSCRIBE, json.dumps(["window"]))
            events.recv()                               # {"success": true}
            last_ok = time.monotonic()
            retile(cmd)
            while True:
                mtype, ev = events.recv()
                if mtype & EVENT_BIT and isinstance(ev, dict) and ev.get("change") in ("focus", "new", "move", "floating"):
                    retile(cmd)
                    last_ok = time.monotonic()
        except (OSError, ConnectionError, ValueError):
            pass                                        # i3 restarted in place, or quit: try again for a while
        finally:
            for s in (events, cmd):
                if s:
                    s.close()
        if time.monotonic() - last_ok > RECONNECT_FOR:
            return 0                                    # i3 is gone (logged out)
        time.sleep(0.5)


def ensure_running():
    """Start the tiler in the background if it is not running (e.g. after it was killed)."""
    path = os.path.join(os.environ.get("XDG_RUNTIME_DIR") or "/tmp", "i3dots-autotiling-%d.lock" % os.getuid())
    try:
        with open(path, "w") as probe:
            fcntl.flock(probe, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(probe, fcntl.LOCK_UN)
    except OSError:
        return                                          # it is running (it holds the lock)
    subprocess.Popen([sys.executable, os.path.abspath(__file__)], start_new_session=True,
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main(argv):
    if "--status" in argv:
        print(read_mode())
        return 0
    if "--toggle" in argv:
        new = "classic" if read_mode() == "dwindle" else "dwindle"
        save_mode(new)
        notify("Spiral (like Hyprland): new windows split the focused one" if new == "dwindle"
               else "Classic: new windows open side by side")
        ensure_running()
        print(new)
        return 0
    if "-h" in argv or "--help" in argv:
        print(__doc__)
        return 0
    return run()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
