#!/usr/bin/env bash
if pgrep -x picom >/dev/null; then pkill -x picom; notify-send -u low "Compositor" "off"
else picom --config "${XDG_CONFIG_HOME:-$HOME/.config}/picom/picom.conf" -b; notify-send -u low "Compositor" "on"; fi
