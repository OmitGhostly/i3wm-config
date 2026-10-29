#!/usr/bin/env bash
# Stay awake: stops the screen from blanking / locking and blocks idle suspend until you turn it off or log out.
# Usage: toggle | on | off | status   (the polybar coffee button calls this)
tag='--who=i3dots-caffeine'
ACCENT=ffffff; . "${XDG_CONFIG_HOME:-$HOME/.config}/i3/accent.conf" 2>/dev/null   # colour chosen in Settings > Colors
[[ $ACCENT =~ ^[0-9a-fA-F]{6}$ ]] || ACCENT=ffffff
is_on() { pgrep -u "$UID" -f -- "systemd-inhibit .*$tag" >/dev/null 2>&1 || [ "$(cat "${XDG_RUNTIME_DIR:-/tmp}/i3dots-caffeine" 2>/dev/null)" = on ]; }
on() {
  is_on && return 0
  xset s off -dpms 2>/dev/null                  # no screensaver blanking / auto-lock, no monitor power-off
  if command -v systemd-inhibit >/dev/null 2>&1; then
    setsid systemd-inhibit --what=idle:sleep "$tag" --why="Stay awake (polybar)" --mode=block sleep infinity >/dev/null 2>&1 &
  fi
  echo on > "${XDG_RUNTIME_DIR:-/tmp}/i3dots-caffeine"
}
off() {
  for p in $(pgrep -u "$UID" -f -- "systemd-inhibit .*$tag" 2>/dev/null); do
    pkill -P "$p" 2>/dev/null; kill "$p" 2>/dev/null     # the 'sleep' it started, then the inhibitor itself
  done
  xset s 600 5 +dpms 2>/dev/null; xset dpms 0 0 720 2>/dev/null   # back to the timers Input.sh sets at login
  rm -f "${XDG_RUNTIME_DIR:-/tmp}/i3dots-caffeine"
}
case "$1" in
  toggle) if is_on; then off; notify-send -u low "Stay awake" "off - the screen can sleep again" 2>/dev/null
          else on; notify-send -u low "Stay awake" "on - the screen will not sleep or lock" 2>/dev/null; fi ;;
  on)  on ;;
  off) off ;;
  status) if is_on; then echo "%{T2}%{F#$ACCENT}󰅶%{F-}%{T-}%{F#$ACCENT} awake%{F-}"; else echo "%{T2}%{F#6e6e6e}󰛊%{F-}%{T-}"; fi ;;
  *) echo "usage: $0 toggle|on|off|status" >&2; exit 1 ;;
esac
