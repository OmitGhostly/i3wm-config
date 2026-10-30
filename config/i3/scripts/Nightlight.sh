#!/usr/bin/env bash
# redshift one-shot (replaces hyprsunset). Usage: toggle | init | status
state="${XDG_CACHE_HOME:-$HOME/.cache}/i3/nightlight"; mkdir -p "$(dirname "$state")"
temp="${NIGHT_TEMP:-4000}"
on()  { redshift -P -O "$temp" >/dev/null 2>&1; echo on > "$state"; }
off() { redshift -x >/dev/null 2>&1; echo off > "$state"; }
case "$1" in
  toggle) icon="${XDG_CONFIG_HOME:-$HOME/.config}/i3/icons/moon.png"
          if [ "$(cat "$state" 2>/dev/null)" = on ]; then off; notify-send -u low -i "$icon" "Night light" "off"
          else on; notify-send -u low -i "$icon" "Night light" "on (${temp}K)"; fi ;;
  init)   if [ "$(cat "$state" 2>/dev/null)" = on ]; then on; fi ;;
  status) if [ "$(cat "$state" 2>/dev/null)" = on ]; then echo "󰖔 ${temp}K"; else echo "󰖙"; fi ;;
esac
