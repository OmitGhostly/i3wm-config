#!/usr/bin/env bash
# NetworkManager's applet (nm-applet), kept running for what it does in the background: it asks for a Wi-Fi
# password when a saved network needs one (a network whose password is kept "for this user only" cannot connect
# without it) and shows VPN prompts. Its tray icon is hidden, since the Wi-Fi item in the bar opens
# Settings > Wi-Fi; switch the icon back on there ("Wi-Fi icon in the tray").
#   NetApplet.sh           hide or show the icon as saved, start the applet if it is not running (i3 runs this)
#   NetApplet.sh restart   the same, restarting the applet
command -v nm-applet >/dev/null 2>&1 || exit 0
# is it running? (ps, not pgrep: a just-killed copy that has not been cleaned up yet must not count)
running() { ps -u "$UID" -o stat=,comm= 2>/dev/null | awk -v n="nm-applet" '$2 == n && $1 !~ /^Z/ {f = 1} END {exit !f}'; }
exec 9>"${XDG_RUNTIME_DIR:-/tmp}/i3dots-netapplet-$UID.lock"
flock -w 10 9 || exit 0
case "${1:-}" in restart|'') ;; *) echo "usage: $0 [restart]" >&2; exit 2 ;; esac
icon=$(python3 "${XDG_CONFIG_HOME:-$HOME/.config}/i3/scripts/SettingsGUI.py" --wifi-icon 2>/dev/null)
if [ "$icon" = on ]; then want=true; else want=false; fi
# the applet's own setting (org.gnome.nm-applet show-applet); an applet without it simply keeps its icon
changed=false
if command -v gsettings >/dev/null 2>&1 && gsettings list-keys org.gnome.nm-applet 2>/dev/null | grep -qx show-applet; then
  if [ "$(gsettings get org.gnome.nm-applet show-applet 2>/dev/null)" != "$want" ]; then
    gsettings set org.gnome.nm-applet show-applet "$want" 2>/dev/null && changed=true
  fi
fi
# a running applet may only read that setting when it starts: restart it when the setting just changed
if [ "${1:-}" = restart ] || [ "$changed" = true ]; then
  pkill -u "$UID" -x nm-applet 2>/dev/null
  for _ in 1 2 3 4 5 6 7 8 9 10; do running || break; sleep 0.1; done
fi
running && exit 0
setsid nm-applet >/dev/null 2>&1 9>&- </dev/null &
# hold the lock until it shows up, so a second call right after this one does not start another copy
for _ in 1 2 3 4 5 6 7 8 9 10; do running && break; sleep 0.1; done
exit 0
