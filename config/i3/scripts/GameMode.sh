#!/usr/bin/env bash
f="${XDG_CACHE_HOME:-$HOME/.cache}/i3/gamemode"; mkdir -p "$(dirname "$f")"
if [ -e "$f" ]; then
  rm "$f"; i3-msg 'gaps inner all set 6; gaps outer all set 4' >/dev/null
  picom --config "${XDG_CONFIG_HOME:-$HOME/.config}/picom/picom.conf" -b
  polybar-msg cmd show >/dev/null 2>&1; notify-send -u low "Game mode" "off"
else
  touch "$f"; i3-msg 'gaps inner all set 0; gaps outer all set 0' >/dev/null
  pkill -x picom; polybar-msg cmd hide >/dev/null 2>&1; notify-send -u low "Game mode" "on"
fi
